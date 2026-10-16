from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_ROOT = "https://api.monid.ai/v1"
RUNS_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "monid"
RUN_LOCK = threading.Lock()
LIMIT_FIELDS = {"maxItems", "maxResults", "resultsLimit", "limit"}


class MonidError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def settings() -> Dict[str, Any]:
    return {"configured": bool(os.environ.get("MONID_API_KEY")),
            "runs_enabled": os.environ.get("MONID_ENABLE_RUNS") == "1",
            "workspace_cap_confirmed": os.environ.get("MONID_WORKSPACE_CAP_CONFIRMED") == "1",
            "max_estimate_usd": str(os.environ.get("MONID_MAX_ESTIMATE_USD", "0.25"))}


def _request(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    key = os.environ.get("MONID_API_KEY", "")
    if not key:
        raise MonidError("未配置 MONID_API_KEY；请在本机环境中设置，不要粘贴到聊天或前端")
    request = Request(API_ROOT + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect).open(request, timeout=35) as response:
            body = response.read(8_000_001)
    except HTTPError as error:
        body = error.read(8_000_001)
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError):
            result = {}
        if isinstance(result, dict) and result.get("runId"):
            return result
        raise MonidError(f"Monid HTTP {error.code}；请检查密钥、余额、权限或接口参数") from None
    except (URLError, TimeoutError, OSError):
        raise MonidError("Monid 网络请求失败；若已提交运行，请先到 Monid 控制台核对，勿重复提交") from None
    if len(body) > 8_000_000:
        raise MonidError("结果超过 8MB，请在 Monid 控制台下载并缩小后续采样量")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeError):
        raise MonidError("Monid 返回了无效 JSON") from None
    if not isinstance(result, dict):
        raise MonidError("Monid 响应结构不符合文档")
    return result


def discover(query: str) -> Dict[str, Any]:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        raise ValueError("请输入 1-1000 字符的接口查询")
    return _request("/discover", {"query": query.strip(), "limit": 5})


def inspect_endpoint(provider: str, endpoint: str) -> Dict[str, Any]:
    if not isinstance(provider, str) or not isinstance(endpoint, str) or not provider or not endpoint.startswith("/"):
        raise ValueError("provider 和 endpoint 无效")
    return _request("/inspect", {"provider": provider, "endpoint": endpoint})


def _money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise MonidError("无法确定费用，已停止运行") from None
    if not amount.is_finite() or amount < 0:
        raise MonidError("费用必须是有限非负数")
    return amount


def estimate_cost(details: Dict[str, Any], inputs: Dict[str, Any]) -> Decimal:
    price = details.get("price") or {}
    amount = price.get("amount") or {}
    if amount.get("currency") != "USD":
        raise MonidError("仅支持可明确预估的 USD 计费接口")
    unit_price = _money(amount.get("value"))
    if price.get("type") == "PER_CALL":
        return unit_price
    if price.get("type") != "PER_RESULT":
        raise MonidError("此计费模式无法预估；请在 Monid 控制台人工执行后导入")
    schema = details.get("input", {}).get("body", {})
    fields = schema.get("properties", {})
    limits = [value for name, value in inputs.items() if name in LIMIT_FIELDS and name in fields]
    if len(limits) != 1 or isinstance(limits[0], bool) or not isinstance(limits[0], int) or not 1 <= limits[0] <= 10:
        raise MonidError("按结果收费的接口必须提供 schema 中的单一条数限制，范围 1-10")
    if any(isinstance(value, list) and len(value) > 1 for value in inputs.values()):
        raise MonidError("首轮每次仅允许一个查询或 URL，避免按查询倍增收费")
    if any(isinstance(value, dict) for value in inputs.values()):
        raise MonidError("复杂嵌套参数无法可靠预估；请在 Monid 控制台人工执行后导入")
    flat = price.get("flatFee") or {"value": 0, "currency": "USD"}
    if flat.get("currency") != "USD":
        raise MonidError("固定费用币种不受支持")
    return unit_price * limits[0] + _money(flat.get("value"))


def _save(job: Dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{job['id']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_job(job_id: str) -> Dict[str, Any]:
    if not isinstance(job_id, str) or len(job_id) != 32 or any(char not in "0123456789abcdef" for char in job_id):
        raise ValueError("无效任务 ID")
    path = RUNS_DIR / f"{job_id}.json"
    if not path.exists():
        raise ValueError("任务不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs() -> list:
    if not RUNS_DIR.exists():
        return []
    jobs = [json.loads(path.read_text(encoding="utf-8")) for path in RUNS_DIR.glob("*.json")]
    return sorted([{key: value for key, value in job.items() if key not in {"input", "result", "inspection"}}
                   for job in jobs], key=lambda job: job["created_at"], reverse=True)[:30]


def prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
    inputs = payload.get("input")
    if not isinstance(inputs, dict):
        raise ValueError("input 必须为 JSON 对象")
    details = inspect_endpoint(payload.get("provider", ""), payload.get("endpoint", ""))
    estimate = estimate_cost(details, inputs)
    if estimate > _money(settings()["max_estimate_usd"]):
        raise MonidError("预估费用超过本地阈值，未创建采集任务")
    job = {"id": uuid.uuid4().hex, "product_id": payload["product_id"], "provider": payload["provider"],
           "endpoint": payload["endpoint"], "input": inputs, "inspection": details,
           "estimate_usd": str(estimate), "status": "PREPARED", "created_at": datetime.now(timezone.utc).isoformat()}
    _save(job)
    return job


def execute(job_id: str, confirmed: bool) -> Dict[str, Any]:
    config = settings()
    if confirmed is not True or not config["runs_enabled"] or not config["workspace_cap_confirmed"]:
        raise MonidError("采集未授权：需启用运行、确认 Monid 工作区硬限额，并勾选本次付费确认")
    with RUN_LOCK:
        job = load_job(job_id)
        if job["status"] != "PREPARED":
            raise MonidError("任务已提交或状态未知；不能重复执行，请刷新或到 Monid 控制台核对")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(job["created_at"])).total_seconds()
        if age > 900 or age < 0:
            raise MonidError("报价已过期，请重新预检")
        details = inspect_endpoint(job["provider"], job["endpoint"])
        estimate = estimate_cost(details, job["input"])
        if estimate > min(_money(job["estimate_usd"]), _money(config["max_estimate_usd"])):
            raise MonidError("报价上涨或超过阈值，请重新预检")
        job["status"] = "SUBMITTING"
        _save(job)
        try:
            result = _request("/run", {"provider": job["provider"], "endpoint": job["endpoint"], "input": job["input"]})
            job.update(status=result.get("status", "UNKNOWN"), run_id=result.get("runId"), result=result)
        except MonidError:
            job["status"] = "UNKNOWN"
            _save(job)
            raise
        _save(job)
        return job


def refresh_job(job_id: str) -> Dict[str, Any]:
    with RUN_LOCK:
        job = load_job(job_id)
        if not job.get("run_id"):
            raise MonidError("没有远程 run ID；请先在 Monid 控制台核对")
        result = _request("/runs/" + quote(job["run_id"], safe=""))
        job.update(status=result.get("status", "UNKNOWN"), result=result)
        _save(job)
        return job