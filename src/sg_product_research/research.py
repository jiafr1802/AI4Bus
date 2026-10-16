from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .model import ScoreResult


EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "evidence.json"

KINDS = {"listing", "review", "social", "supplier"}
REQUIREMENTS = {"listing": 3, "review": 5, "social": 2, "supplier": 1}
LABELS = {"listing": "新加坡商品", "review": "新加坡评论", "social": "社媒内容", "supplier": "供应商报价"}


def normalize_evidence(record: Dict[str, Any], product_ids: Iterable[str], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    if not isinstance(record, dict):
        raise ValueError("每条证据必须是 JSON 对象")
    if any(value is not None and not isinstance(value, (str, int, float)) for value in record.values()):
        raise ValueError("证据字段必须是文本或数字")
    result = {field: str(record.get(field) if record.get(field) is not None else "").strip() for field in (
        "product_id", "platform", "kind", "market", "observed_at", "url", "text", "source_id", "title", "tags", "collection_id", "published_at",
    )}
    excluded = record.get("excluded", False)
    if excluded not in (True, False, "true", "false"):
        raise ValueError("excluded 必须为 true 或 false")
    result["excluded"] = excluded is True or excluded == "true"
    if result["product_id"] not in product_ids:
        raise ValueError("未知候选产品")
    result["platform"] = result["platform"].lower()
    aliases = {"amazon-sg": "amazon", "amazon.sg": "amazon", "youtu.be": "youtube", "youtube.com": "youtube",
               "lazada-sg": "lazada", "shopee-sg": "shopee"}
    result["platform"] = aliases.get(result["platform"], result["platform"])
    result["market"] = result["market"].upper()
    if result["kind"] not in KINDS:
        raise ValueError("kind 必须为 listing/review/social/supplier")
    if not result["platform"] or not result["text"] or not result["market"]:
        raise ValueError("platform、market、text 不可为空；未知市场请使用 UNKNOWN")
    for field in ("observed_at", "published_at"):
        if result[field]:
            value = result[field]
            result[field] = (datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                             if "T" in value or " " in value else date.fromisoformat(value)).isoformat()
    observed = date.fromisoformat(result["observed_at"])
    if observed > today:
        raise ValueError("证据日期不能在未来")
    if result["published_at"] and date.fromisoformat(result["published_at"]) > observed:
        raise ValueError("发布日期不能晚于观察日期")
    parsed = urlsplit(result["url"])
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("证据需要有效的公开 HTTP(S) 来源链接")
    query = urlencode([(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                       if not key.lower().startswith("utm_")])
    result["url"] = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, query, ""))
    fallback_id = result["url"]
    if result["kind"] in {"review", "social"}:
        fallback_id += "\n" + " ".join(result["text"].split())
    identity = [result["product_id"], result["platform"], result["kind"], result["source_id"] or fallback_id]
    result["id"] = hashlib.sha256("\n".join(identity).encode()).hexdigest()[:24]
    return result


def merge_evidence(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]], product_ids: Iterable[str]) -> Dict[str, Any]:
    if len(incoming) > 1000:
        raise ValueError("单次最多导入 1000 条证据")
    valid_ids = set(product_ids)
    normalized = [normalize_evidence(record, valid_ids) for record in incoming]
    merged = {record["id"]: record for record in existing}
    added = 0
    updated = 0
    for record in normalized:
        previous = merged.get(record["id"])
        if previous is None:
            added += 1
            merged[record["id"]] = record
        elif record["observed_at"] >= previous["observed_at"] and record != previous:
            updated += 1
            merged[record["id"]] = record
    return {"records": list(merged.values()), "added": added, "updated": updated,
            "duplicates": len(incoming) - added - updated}


def summarize_evidence(records: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    unique = {record["id"]: record for record in records}.values()
    included = [record for record in unique if not record.get("excluded", False)]
    fresh = [record for record in included if 0 <= (today - date.fromisoformat(
        record.get("published_at") or record["observed_at"]
    )).days <= 30]
    eligible = [record for record in fresh if record["kind"] in {"social", "supplier"} or record["market"] == "SG"]
    counts = Counter(record["kind"] for record in eligible)
    platforms = sorted({record["platform"] for record in eligible if record["kind"] != "supplier"})
    gaps = [f"{LABELS[kind]}还缺 {max(0, minimum - counts[kind])} 条"
            for kind, minimum in REQUIREMENTS.items() if counts[kind] < minimum]
    if len(platforms) < 2:
        gaps.append("至少需要两个独立需求平台交叉验证")
    themes = Counter(tag.strip() for record in eligible if record["kind"] in {"review", "social"}
                     for tag in set(record.get("tags", "").split("|")) if tag.strip())
    coverage = round(sum(min(counts[kind] / minimum, 1) for kind, minimum in REQUIREMENTS.items()) / 4 * 100)
    return {"total": len(unique), "fresh": len(fresh), "stale": len(included) - len(fresh), "excluded": len(unique) - len(included),
            "counts": dict(counts), "platforms": platforms, "coverage": coverage,
            "ready": not gaps, "gaps": gaps, "themes": [{"tag": tag, "count": count} for tag, count in themes.most_common(8)],
            "requirements": REQUIREMENTS, "freshness_days": 30}


def load_evidence(path: Path) -> List[Dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(records, list):
        raise ValueError("证据文件必须为 JSON 数组")
    historical = []
    for platform in ("amazon", "lazada"):
        for sample in sorted((path.parent / "samples").glob(f"????-??-??-{platform}-cable-management.csv")):
            observed = sample.name[:10]
            if date.fromisoformat(observed) > date.today():
                continue
            with sample.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    historical.append(normalize_evidence({
                        "product_id": "cable-sleeve", "platform": platform, "kind": "listing",
                        "market": "UNKNOWN" if platform == "amazon" else "SG", "observed_at": observed,
                        "source_id": row.get("asin") or row.get("item_id"), "url": row["url"], "title": row["title"],
                        "text": json.dumps(row, ensure_ascii=False), "collection_id": sample.name,
                    }, ["cable-sleeve"]))
    merged = {}
    for record in historical + records:
        previous = merged.get(record["id"])
        if previous is None or record["observed_at"] >= previous["observed_at"]:
            merged[record["id"]] = record
    return list(merged.values())


def evidence_gate(result: ScoreResult, summary: Dict[str, Any]) -> ScoreResult:
    if result.decision == "TEST" and not summary["ready"]:
        return replace(result, decision="WATCH", reason="模型达标，但近期交叉证据不足；先补证据")
    return result


def parse_import(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "records" in payload:
        records = payload["records"]
    elif payload.get("format") == "csv":
        records = list(csv.DictReader(io.StringIO(str(payload.get("content", "")).lstrip("\ufeff"))))
    else:
        records = json.loads(str(payload.get("content", "")).lstrip("\ufeff"))
    if not isinstance(records, list) or not records:
        raise ValueError("证据必须为非空 JSON 数组或带表头的 CSV")
    return records


def json_pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ValueError("字段路径必须使用 JSON Pointer，例如 /items 或 /review/text；根数组路径留空")
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError):
            raise ValueError(f"返回数据中找不到字段路径: {pointer}") from None
    return value


def map_output(output: Any, payload: Dict[str, Any], product_ids: Iterable[str]) -> List[Dict[str, Any]]:
    items = json_pointer(output, payload.get("items_path", ""))
    mapping = payload.get("mapping", {})
    defaults = payload.get("defaults", {})
    if not isinstance(items, list) or not 1 <= len(items) <= 1000:
        raise ValueError("结果路径必须指向 1-1000 条记录的数组")
    if not isinstance(mapping, dict) or not isinstance(defaults, dict):
        raise ValueError("mapping 和 defaults 必须为 JSON 对象")
    records = []
    for item in items:
        record = {**defaults, **{field: json_pointer(item, pointer) for field, pointer in mapping.items()}}
        records.append(normalize_evidence(record, product_ids))
    return records