from __future__ import annotations

import unittest
from datetime import date, timedelta

from sg_product_research.research import merge_evidence, normalize_evidence, summarize_evidence
from sg_product_research.research import evidence_gate, load_evidence, map_output, parse_import
from pathlib import Path
from sg_product_research.model import ScoreResult


def evidence(**changes):
    record = {"product_id": "cable-sleeve", "platform": "Amazon", "kind": "review", "market": "SG",
              "observed_at": date.today().isoformat(), "url": "https://example.com/review/1", "text": "Adhesive failed",
              "tags": "adhesive"}
    record.update(changes)
    return record


class EvidenceTests(unittest.TestCase):
    def test_excluded_evidence_is_retained_but_not_counted(self):
        record = normalize_evidence(evidence(excluded=True), ["cable-sleeve"])
        summary = summarize_evidence([record])
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["excluded"], 1)
        self.assertEqual(summary["counts"], {})

    def test_iso_timestamp_mapping_preserves_source_date(self):
        record = normalize_evidence(evidence(observed_at="2026-09-06T16:50:00+08:00", published_at="2026-09-01T12:00:00Z"), ["cable-sleeve"])
        self.assertEqual(record["observed_at"], "2026-09-06")
        self.assertEqual(record["published_at"], "2026-09-01")

    def test_historical_samples_keep_original_dates_and_market_caveat(self):
        records = load_evidence(Path(__file__).resolve().parents[1] / "data" / "evidence.json")
        historical = [record for record in records if record.get("collection_id", "").endswith(".csv")]
        self.assertEqual(len(historical), 40)
        self.assertTrue(all(record["observed_at"] == "2026-09-06" for record in historical))
        self.assertTrue(all(record["market"] == "UNKNOWN" for record in historical if record["platform"] == "amazon"))

    def test_listing_text_changes_do_not_inflate_unique_products(self):
        records = [evidence(kind="listing", text="price one"), evidence(kind="listing", text="price two")]
        result = merge_evidence([], records, ["cable-sleeve"])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["text"], "price two")

    def test_csv_and_explicit_nested_mapping(self):
        self.assertEqual(parse_import({"format": "csv", "content": "product_id,text\ncable-sleeve,review\n"})[0]["text"], "review")
        records = map_output({"items": [{"review": {"body": "Too short"}, "link": "https://example.com/review"}]},
                             {"items_path": "/items", "mapping": {"text": "/review/body", "url": "/link"},
                              "defaults": evidence()}, ["cable-sleeve"])
        self.assertEqual(records[0]["text"], "Too short")
        with self.assertRaises(ValueError):
            map_output([], {"items_path": "/missing"}, ["cable-sleeve"])

    def test_old_publication_does_not_become_fresh_when_collected_today(self):
        record = normalize_evidence(evidence(published_at=(date.today() - timedelta(days=45)).isoformat()), ["cable-sleeve"])
        self.assertEqual(summarize_evidence([record])["counts"], {})

    def test_null_text_and_unsafe_links_are_rejected(self):
        for record in (evidence(text=None), evidence(url="javascript:alert(1)"), evidence(url="https://user:secret@example.com")):
            with self.assertRaises(ValueError):
                normalize_evidence(record, ["cable-sleeve"])

    def test_tracking_parameters_and_platform_aliases_do_not_duplicate(self):
        records = [evidence(platform="amazon-sg", url="https://example.com/review?utm_source=one"),
                   evidence(platform="amazon", url="https://example.com/review?utm_source=two")]
        self.assertEqual(merge_evidence([], records, ["cable-sleeve"])["added"], 1)

    def test_evidence_gate_never_promotes_a_blocked_product(self):
        for decision in ("BLOCK", "DROP", "WATCH"):
            result = ScoreResult(80, 4, 0.4, decision, "original")
            self.assertEqual(evidence_gate(result, {"ready": True}).decision, decision)
        result = ScoreResult(80, 4, 0.4, "TEST", "original")
        self.assertEqual(evidence_gate(result, {"ready": False}).decision, "WATCH")

    def test_repeated_import_is_idempotent(self):
        first = merge_evidence([], [evidence(), evidence()], ["cable-sleeve"])
        second = merge_evidence(first["records"], [evidence()], ["cable-sleeve"])
        self.assertEqual(first["added"], 1)
        self.assertEqual(second["added"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(summarize_evidence(second["records"])["counts"], {"review": 1})

    def test_old_and_foreign_reviews_do_not_count_as_local_demand(self):
        records = [evidence(source_id="old", observed_at=(date.today() - timedelta(days=31)).isoformat()),
                   evidence(source_id="foreign", market="US")]
        summary = summarize_evidence(merge_evidence([], records, ["cable-sleeve"])["records"])
        self.assertEqual(summary["stale"], 1)
        self.assertEqual(summary["counts"], {})
        self.assertFalse(summary["ready"])

    def test_future_dates_and_unknown_candidates_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_evidence(evidence(observed_at=(date.today() + timedelta(days=1)).isoformat()), ["cable-sleeve"])
        with self.assertRaises(ValueError):
            normalize_evidence(evidence(product_id="missing"), ["cable-sleeve"])

    def test_complete_cross_platform_evidence_is_research_ready(self):
        records = [evidence(kind=kind, source_id=f"{kind}-{index}", platform="youtube" if kind == "social" else "amazon")
                   for kind, minimum in {"listing": 3, "review": 5, "social": 2, "supplier": 1}.items()
                   for index in range(minimum)]
        summary = summarize_evidence(merge_evidence([], records, ["cable-sleeve"])["records"])
        self.assertTrue(summary["ready"])
        self.assertEqual(summary["coverage"], 100)
        self.assertEqual(summary["themes"], [{"tag": "adhesive", "count": 7}])


if __name__ == "__main__":
    unittest.main()