from __future__ import annotations

import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"


def read_csv(name: str) -> list[dict[str, str]]:
    with (SAMPLES / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ResearchDataTests(unittest.TestCase):
    def test_amazon_sample_has_twenty_unique_ranked_rows(self) -> None:
        rows = read_csv("2026-09-06-amazon-cable-management.csv")

        self.assertEqual(len(rows), 20)
        self.assertEqual({int(row["rank"]) for row in rows}, set(range(1, 21)))
        self.assertEqual(len({row["asin"] for row in rows}), 20)

    def test_supplier_references_are_distinct_and_not_quotes(self) -> None:
        rows = read_csv("2026-09-06-supplier-public-listings.csv")

        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["supplier"] for row in rows}), 3)
        self.assertTrue(all(row["status"] == "public_listing" for row in rows))
        self.assertTrue(all(row["missing_before_purchase"] for row in rows))

    def test_lazada_sample_has_twenty_unique_ranked_rows(self) -> None:
        rows = read_csv("2026-09-06-lazada-cable-management.csv")

        self.assertEqual(len(rows), 20)
        self.assertEqual({int(row["rank"]) for row in rows}, set(range(1, 21)))
        self.assertEqual(len({row["item_id"] for row in rows}), 20)
        self.assertTrue(all(float(row["price_sgd"]) > 0 for row in rows))
        self.assertTrue(all(int(row["sold_count"]) >= 0 for row in rows))

    def test_blocked_marketplaces_record_access_reason(self) -> None:
        rows = read_csv("2026-09-06-marketplace-access.csv")
        blocked = [row for row in rows if row["status"] != "accessible"]

        self.assertGreaterEqual(len(blocked), 3)
        self.assertTrue(all(row["notes"] for row in blocked))

    def test_lazada_access_record_matches_sample(self) -> None:
        rows = read_csv("2026-09-06-marketplace-access.csv")
        lazada = next(row for row in rows if row["marketplace"] == "Lazada")

        self.assertEqual(lazada["status"], "accessible")
        self.assertGreater(int(lazada["result_count"]), 20)


if __name__ == "__main__":
    unittest.main()