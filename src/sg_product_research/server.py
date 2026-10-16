from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import threading
from dataclasses import asdict
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import median
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from . import monid
from .cli import NUMERIC_FIELDS, load_candidates, write_outputs
from .model import score_candidate
from .research import EVIDENCE_PATH, evidence_gate, load_evidence, map_output, merge_evidence, parse_import, summarize_evidence


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CANDIDATES_PATH = DATA_DIR / "candidates.csv"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUT_DIR = ROOT / "generated"
STATIC_DIR = ROOT / "static"
EDITABLE_TEXT_FIELDS = {"evidence_note"}
WRITE_LOCK = threading.Lock()


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _latest_snapshot(suffix: str):
    paths = sorted(path for path in SAMPLES_DIR.glob(f"????-??-??-{suffix}.csv") if path.name[:10] <= date.today().isoformat())
    if not paths:
        return [], None
    return _read_csv(paths[-1]), paths[-1].name[:10]


def _dashboard_data() -> Dict[str, Any]:
    evidence = load_evidence(EVIDENCE_PATH)
    candidates = []
    for raw, candidate in load_candidates(CANDIDATES_PATH):
        model_result = score_candidate(candidate)
        summary = summarize_evidence([record for record in evidence if record["product_id"] == candidate.product_id])
        result = evidence_gate(model_result, summary)
        candidates.append({**raw, **asdict(result), "model_decision": model_result.decision, "research": summary})
    candidates.sort(key=lambda row: row["score"], reverse=True)

    lazada, sampled_at = _latest_snapshot("lazada-cable-management")
    access, access_date = _latest_snapshot("marketplace-access")

    sold = sorted(int(row["sold_count"]) for row in lazada)
    prices = sorted(float(row["price_sgd"]) for row in lazada)
    return {
        "candidates": candidates,
        "evidence": evidence,
        "marketplace_access": access,
        "marketplace_access_date": access_date,
        "lazada_summary": {
            "sample_size": len(lazada),
            "sampled_at": sampled_at,
            "stale": bool(sampled_at and (date.today() - date.fromisoformat(sampled_at)).days > 30),
            "median_price_sgd": median(prices) if lazada else None,
            "median_sold_count": median(sold) if lazada else None,
            "max_sold_count": max(sold) if sold else None,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _update_candidate(product_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    allowed = set(NUMERIC_FIELDS) | EDITABLE_TEXT_FIELDS
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"不可编辑字段: {', '.join(sorted(unknown))}")

    with WRITE_LOCK:
        with CANDIDATES_PATH.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            rows = list(reader)
        if not fieldnames:
            raise ValueError("候选数据缺少表头")

        target = next((row for row in rows if row["product_id"] == product_id), None)
        if target is None:
            raise KeyError(product_id)

        for field, value in changes.items():
            if field in NUMERIC_FIELDS:
                converted = NUMERIC_FIELDS[field](value)
                target[field] = str(converted)
            else:
                target[field] = str(value).strip()

        temporary = CANDIDATES_PATH.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        try:
            validated = load_candidates(temporary)
            for _, candidate in validated:
                score_candidate(candidate)
            temporary.replace(CANDIDATES_PATH)
        finally:
            temporary.unlink(missing_ok=True)

        write_outputs(load_candidates(CANDIDATES_PATH), OUTPUT_DIR, EVIDENCE_PATH)
        updated = next(row for row in _dashboard_data()["candidates"] if row["product_id"] == product_id)
        return updated


def _persist_evidence(records: List[Dict[str, Any]]) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE_PATH.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(EVIDENCE_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    write_outputs(load_candidates(CANDIDATES_PATH), OUTPUT_DIR, EVIDENCE_PATH)


def _import_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    records = parse_import(payload)
    with WRITE_LOCK:
        valid_ids = [candidate.product_id for _, candidate in load_candidates(CANDIDATES_PATH)]
        result = merge_evidence(load_evidence(EVIDENCE_PATH), records, valid_ids)
        _persist_evidence(result["records"])
    return {key: value for key, value in result.items() if key != "records"}


def _exclude_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload.get("excluded"), bool):
        raise ValueError("excluded 必须为布尔值")
    with WRITE_LOCK:
        records = load_evidence(EVIDENCE_PATH)
        target = next((record for record in records if record["id"] == payload.get("id")), None)
        if target is None:
            raise ValueError("证据不存在")
        target["excluded"] = payload["excluded"]
        _persist_evidence(records)
    return {"id": target["id"], "excluded": target["excluded"]}


def _monid_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if action == "discover":
        return monid.discover(payload.get("query", ""))
    if action == "inspect":
        return monid.inspect_endpoint(payload.get("provider", ""), payload.get("endpoint", ""))
    if action == "prepare":
        if payload.get("product_id") not in {candidate.product_id for _, candidate in load_candidates(CANDIDATES_PATH)}:
            raise ValueError("请选择有效候选产品")
        return monid.prepare(payload)
    if action == "execute":
        return monid.execute(payload.get("id", ""), payload.get("confirmed", False))
    if action == "refresh":
        return monid.refresh_job(payload.get("id", ""))
    if action in {"load", "preview"}:
        job = monid.load_job(payload.get("id", ""))
        if action == "load":
            return job
        result = job.get("result", {})
        if result.get("status") != "COMPLETED" or result.get("providerResponse", {}).get("httpStatus", 200) >= 400:
            raise ValueError("任务未成功返回数据；请检查任务状态及供应商 HTTP 状态")
        defaults = payload.get("defaults", {})
        if not isinstance(defaults, dict):
            raise ValueError("defaults 必须为 JSON 对象")
        mapping_payload = {**payload, "defaults": {**defaults, "collection_id": job["id"], "product_id": job["product_id"]}}
        records = map_output(result.get("output"), mapping_payload,
                             [candidate.product_id for _, candidate in load_candidates(CANDIDATES_PATH)])
        if any(record["product_id"] != job["product_id"] for record in records):
            raise ValueError("采集结果必须关联原任务候选")
        return {"records": records}
    raise ValueError("未知 Monid 操作")


class ResearchHandler(BaseHTTPRequestHandler):
    server_version = "SGResearch/0.1"

    def _is_local_request(self) -> bool:
        host = urlparse("//" + self.headers.get("Host", "")).hostname
        if host not in {"127.0.0.1", "localhost", "::1"}:
            self._send_json({"error": "后台仅接受本机 Host"}, HTTPStatus.FORBIDDEN)
            return False
        return True

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 2_000_000:
            raise ValueError("请求内容过大")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("请求必须是 JSON 对象")
        return payload

    def _serve_static(self, requested_path: str) -> None:
        relative = "index.html" if requested_path == "/" else requested_path.lstrip("/")
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._is_local_request():
            return
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            self._send_json(_dashboard_data())
            return
        if path == "/api/monid/status":
            self._send_json({**monid.settings(), "jobs": monid.list_jobs()})
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        if not self._is_local_request():
            return
        path = urlparse(self.path).path
        try:
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                self._send_json({"error": "不允许跨站写入"}, HTTPStatus.FORBIDDEN)
                return
            if path == "/api/evidence/import":
                self._send_json(_import_evidence(self._read_json()))
                return
            if path == "/api/evidence/exclude":
                self._send_json(_exclude_evidence(self._read_json()))
                return
            if path.startswith("/api/monid/"):
                self._send_json(_monid_action(path.rsplit("/", 1)[-1], self._read_json()))
                return
            if path == "/api/recalculate":
                with WRITE_LOCK:
                    write_outputs(load_candidates(CANDIDATES_PATH), OUTPUT_DIR, EVIDENCE_PATH)
                self._send_json(_dashboard_data())
                return
            prefix = "/api/candidates/"
            if path.startswith(prefix):
                product_id = unquote(path[len(prefix):])
                updated = _update_candidate(product_id, self._read_json())
                self._send_json(updated)
                return
            self._send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except KeyError:
            self._send_json({"error": "候选不存在"}, HTTPStatus.NOT_FOUND)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动新加坡选品本地管理后台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ResearchHandler)
    print(f"Management console: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()