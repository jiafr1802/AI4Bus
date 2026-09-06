from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sg_product_research import server


ROOT = Path(__file__).resolve().parents[1]


class ManagementServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidates = self.root / "candidates.csv"
        self.candidates.write_bytes((ROOT / "data" / "candidates.csv").read_bytes())
        self.output = self.root / "generated"
        self.patches = [
            patch.object(server, "CANDIDATES_PATH", self.candidates),
            patch.object(server, "OUTPUT_DIR", self.output),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self) -> None:
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temporary.cleanup()

    def test_update_candidate_persists_and_regenerates_ranking(self) -> None:
        updated = server._update_candidate("cable-sleeve", {"demand_score": 87})

        with self.candidates.open(encoding="utf-8-sig", newline="") as handle:
            row = next(row for row in csv.DictReader(handle) if row["product_id"] == "cable-sleeve")
        self.assertEqual(row["demand_score"], "87.0")
        self.assertEqual(float(updated["demand_score"]), 87.0)
        self.assertTrue((self.output / "ranking.csv").exists())

    def test_invalid_score_does_not_replace_candidate_data(self) -> None:
        original = self.candidates.read_bytes()

        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            server._update_candidate("cable-sleeve", {"demand_score": 101})

        self.assertEqual(self.candidates.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()