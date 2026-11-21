"""Save one explicitly approved KaloData query without automatic retries."""

import argparse
import datetime
from decimal import Decimal
import hashlib
import http.client
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "kalodata-life-aesthetics"
BASE = "https://www.kalodata.com/openapi/v1"


def query_spec(args):
    body = {
        "region": "SG", "language": "zh-CN", "currency": "SGD",
        "date_range": "last30Day",
    }
    if args.kind == "detail":
        if not args.product:
            raise ValueError("detail requires --product")
        body.update(product_id=args.product, need_extra=True)
        return "/tiktok/product/detail", body
    body.update(
        page_size=args.limit, page_number=1,
        sort_field={"field": "revenue", "type": "DESC"},
    )
    if args.category:
        body["category_ids"] = [args.category]
    if args.kind == "categories":
        body["category_level"] = args.level
        return "/tiktok/category/rank", body
    if not args.category:
        raise ValueError("products requires a verified --category ID")
    return "/tiktok/product/rank", body


def collect(path, body, api_key, directory=RAW, max_attempts=10, max_credits=1):
    directory.mkdir(parents=True, exist_ok=True)
    costs = {
        "/tiktok/category/rank": "0.1",
        "/tiktok/product/rank": "0.1",
        "/tiktok/product/detail": "0.1",
        "/tiktok/shop/detail": "0.1",
        "/tiktok/product/comments": "0.01",
        "/tiktok/product/images": "0.01",
    }
    if path not in costs or body.get("page_size", 100) > 100:
        raise ValueError("Unsupported endpoint or page size for this budget.")
    cost = Decimal(costs[path])
    attempts = list(directory.glob("*.json"))
    if len(attempts) >= max_attempts:
        raise ValueError("Attempt limit reached. Review billing before continuing.")
    spent = sum(
        (Decimal(str(json.loads(attempt.read_text())["estimated_credits"])) for attempt in attempts),
        Decimal("0"),
    )
    if spent + cost > Decimal(str(max_credits)):
        raise ValueError("Credit estimate limit reached. No new request sent.")
    budget = directory / "audit" / "budget.json"
    budget.parent.mkdir(parents=True, exist_ok=True)
    limits = {"max_attempts": max_attempts, "max_credits": str(max_credits)}
    if budget.exists():
        if json.loads(budget.read_text()) != limits:
            raise ValueError("Round budget cannot be changed after collection starts.")
    else:
        budget.write_text(json.dumps(limits, indent=2), encoding="utf-8")
    day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    signature = json.dumps([day, path, body], sort_keys=True).encode("utf-8")
    target = directory / (hashlib.sha256(signature).hexdigest()[:16] + ".json")
    record = {
        "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "endpoint": BASE + path, "request": body,
        "estimated_credits": float(cost), "actual_credits": None,
        "status": "attempted; outcome and billing unknown",
    }
    with target.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    request = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={
            "secret-key": api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "Connection": "close",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        envelope = json.loads(json.dumps(envelope).replace(api_key, "[REDACTED]"))
        if not isinstance(envelope, dict) or envelope.get("success") is not True:
            record["status"] = "API rejected query; check account before retrying"
            if isinstance(envelope, dict):
                record["response"] = envelope
        else:
            record["status"] = "success"
            record["response"] = envelope
    except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException):
        record["status"] = "response unavailable; check account before retrying"
    finally:
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("categories", "products", "detail"))
    parser.add_argument("--category")
    parser.add_argument("--product")
    parser.add_argument("--level", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--limit", type=int, choices=range(1, 101), default=100)
    parser.add_argument("--approve", action="store_true", help="Approve one estimated 0.1-credit query")
    args = parser.parse_args()
    try:
        path, body = query_spec(args)
        if not args.approve:
            print(json.dumps({"endpoint": BASE + path, "request": body, "estimated_credits": 0.1}, indent=2))
            print("Preview only. Add --approve to send one request.")
            return 0
        api_key = os.environ.get("KALODATA_API_KEY")
        if not api_key:
            print("Key is unavailable in this terminal. Run in the terminal where you exported it.")
            return 2
        target, record = collect(path, body, api_key)
        print(str(target.relative_to(ROOT)))
        print(record["status"])
        return 0 if record["status"] == "success" else 1
    except (ValueError, FileExistsError) as error:
        print("Stopped: {}. No new request sent.".format(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())