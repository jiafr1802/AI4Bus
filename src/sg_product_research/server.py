from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from .cli import NUMERIC_FIELDS, load_candidates, write_outputs
from .model import score_candidate


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


def _dashboard_data() -> Dict[str, Any]:
    candidates = []
    for raw, candidate in load_candidates(CANDIDATES_PATH):
        result = score_candidate(candidate)
        candidates.append({**raw, **asdict(result)})
    candidates.sort(key=lambda row: row["score"], reverse=True)

    lazada_path = SAMPLES_DIR / "2026-09-06-lazada-cable-management.csv"
    lazada = _read_csv(lazada_path) if lazada_path.exists() else []
    access_path = SAMPLES_DIR / "2026-09-06-marketplace-access.csv"
    access = _read_csv(access_path) if access_path.exists() else []

    sold = sorted(int(row["sold_count"]) for row in lazada)
    prices = sorted(float(row["price_sgd"]) for row in lazada)
    middle = len(lazada) // 2
    return {
        "candidates": candidates,
        "marketplace_access": access,
        "lazada_summary": {
            "sample_size": len(lazada),
            "median_price_sgd": (prices[middle - 1] + prices[middle]) / 2 if lazada else None,
            "median_sold_count": (sold[middle - 1] + sold[middle]) / 2 if lazada else None,
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

        write_outputs(load_candidates(CANDIDATES_PATH), OUTPUT_DIR)
        updated = next(row for row in _dashboard_data()["candidates"] if row["product_id"] == product_id)
        return updated


class ResearchHandler(BaseHTTPRequestHandler):
    server_version = "SGResearch/0.1"

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
        if length > 64_000:
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
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            self._send_json(_dashboard_data())
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/recalculate":
                write_outputs(load_candidates(CANDIDATES_PATH), OUTPUT_DIR)
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