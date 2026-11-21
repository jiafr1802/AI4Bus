import csv
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/kalodata-search-case-2026-11-21"
PERIOD = "2026-10-21~2026-11-19"
WEEKS = ("2026-11-06~2026-11-12", "2026-11-13~2026-11-19")
SELECTED = {
    "1733112519268992114": "SNUGSG E-B001",
    "1729570469485839492": "JIAJIA",
    "1729553854526358948": "Simplee Street SH288",
    "1734257482384245988": "LivelyHome.sg",
    "1733788464777233807": "Za Huo Dian",
    "1737239825686562474": "MORI SPACE",
}
RESERVE_RANKS = {11, 42, 49, 51, 53, 54, 58, 59, 67, 70, 73, 82, 89, 90, 94, 97}
UNCLEAR_RANKS = {14, 16, 26, 34, 37, 78, 84, 92, 98}
SG = timezone(timedelta(hours=8))


def analyze():
    records = [dict(json.loads(path.read_text()), file=path.name) for path in sorted(RAW.glob("*.json"))]
    successful = [record for record in records if record["status"] == "success"]
    rank_records = [record for record in successful if record["endpoint"].endswith("/rank")]
    leaf = next(record for record in rank_records if record["request"]["category_ids"] == ["600621"])
    leaf_ranks = {product["product_id"]: rank for rank, product in enumerate(leaf["response"]["data"], 1)}
    products = {}
    for record in [leaf] + [record for record in rank_records if record is not leaf]:
        for product in record["response"]["data"]:
            product_id = product["product_id"]
            if product_id not in products:
                products[product_id] = dict(product, sources=[])
            products[product_id]["sources"].append(record["file"])
    ledger = []
    for product_id, product in products.items():
        rank = leaf_ranks.get(product_id)
        if product_id in SELECTED:
            decision, reason = "deep_dive", "Purposeful six-product sample; not a best-product ranking"
        elif rank in RESERVE_RANKS:
            decision, reason = "reserve", "Adjacent organizer; specifications not verified; not rejected"
        elif rank in UNCLEAR_RANKS:
            decision, reason = "unverified", "Generic title; function and specifications require verification"
        elif rank is None and "Moon Nude" in product["product_name"]:
            decision, reason = "reserve", "Relevant vanity alternative; not queried under this budget"
        elif rank is None and product_id == "1729631693437699511":
            decision, reason = "reserve", "Vanity tray; different structure and only one reported period sale"
        else:
            decision, reason = "outside_scope", "Different or unconfirmed use from the selected tabletop organizer case"
        ledger.append({
            "product_id": product_id, "product_name": product["product_name"],
            "seller_id": product.get("seller_id"), "seller_name": product.get("seller_name"),
            "revenue_sgd": product["revenue"], "sales_volume": product["sales_volumn"],
            "unit_price_sgd": product["unit_price"], "sku_count": product.get("sku_count"),
            "leaf_rank": rank, "query_sources": ";".join(product["sources"]),
            "decision": decision, "reason": reason,
        })
    details = {
        (record["request"]["product_id"], record["request"]["date_range"]): record
        for record in records if record["endpoint"].endswith("/detail")
    }
    comments = {
        record["request"]["product_id"]: record["response"]["data"]
        for record in successful if record["endpoint"].endswith("/comments")
    }
    summary = []
    for product_id, label in SELECTED.items():
        baseline = details[(product_id, PERIOD)]["response"]["data"]
        weeks = [details[(product_id, period)].get("response", {}).get("data") for period in WEEKS]
        reviews = comments[product_id]
        dates = [datetime.fromtimestamp(review["review_timestamp"], SG).date().isoformat() for review in reviews]
        assert len({review["review_id"] for review in reviews}) == len(reviews)
        assert all(review["product_id"] == product_id and 1 <= review["rating"] <= 5 for review in reviews)
        assert all(reviews[index]["review_timestamp"] >= reviews[index + 1]["review_timestamp"] for index in range(len(reviews) - 1))
        changes = {
            field: (weeks[1][field] / weeks[0][field] - 1) * 100 if all(weeks) and weeks[0][field] else None
            for field in ("revenue", "sales_volumn")
        }
        summary.append({
            "product_id": product_id, "label": label,
            "baseline": {field: baseline.get(field) for field in (
                "revenue", "sales_volumn", "unit_price", "min_price", "max_price", "delivery_type",
                "product_shop_id", "product_review_count", "shopping_mall_revenue", "video_revenue", "live_revenue",
            )},
            "weeks": [{field: week[field] for field in ("revenue", "sales_volumn", "unit_price")} if week else None for week in weeks],
            "changes_percent": changes,
            "reviews": {
                "rows": len(reviews), "nonempty": sum(bool(review["display_text"].strip()) for review in reviews),
                "low_ratings": sum(review["rating"] <= 3 for review in reviews),
                "low_ratings_with_text": sum(review["rating"] <= 3 and bool(review["display_text"].strip()) for review in reviews),
                "sku_count": len({review["sku_id"] for review in reviews}),
                "oldest_sg": min(dates), "newest_sg": max(dates),
                "weekly_counts": [sum(period.split("~")[0] <= date <= period.split("~")[1] for date in dates) for period in WEEKS],
            },
        })
    before = json.loads((RAW / "audit/before.json").read_text())["balance"]["totalRemain"]
    after = json.loads((RAW / "audit/after.json").read_text())["balance"]["totalRemain"]
    spent = Decimal(str(before)) - Decimal(str(after))
    estimated = sum((Decimal(str(record["estimated_credits"])) for record in records), Decimal(0))
    assert spent == estimated == Decimal("2.36")
    assert len(products) == 107 and len(records) == 29 and len(successful) == 28
    assert sum(item["reviews"]["rows"] for item in summary) == 384
    assert sum(all(item["weeks"]) for item in summary) == 5
    assert sum(item["decision"] == "deep_dive" for item in ledger) == 6
    output = ROOT / "generated/sg-storage-screening.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger[0]))
        writer.writeheader()
        writer.writerows(ledger)
    result = {"period": PERIOD, "week_ranges": WEEKS, "distinct_products": len(products), "credits_spent": str(spent), "products": summary}
    (RAW / "audit/analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    analyze()