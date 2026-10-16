from __future__ import annotations

import csv
import http.client
import json
import tempfile
import threading
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
        self.evidence = self.root / "evidence.json"
        self.patches = [
            patch.object(server, "CANDIDATES_PATH", self.candidates),
            patch.object(server, "OUTPUT_DIR", self.output),
            patch.object(server, "EVIDENCE_PATH", self.evidence),
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

    def test_import_is_atomic_and_duplicate_safe(self) -> None:
        from datetime import date
        record = {"product_id": "cable-sleeve", "platform": "amazon", "kind": "review", "market": "SG",
                  "observed_at": date.today().isoformat(), "url": "https://example.com/review", "text": "Too short"}
        result = server._import_evidence({"records": [record, record]})
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["duplicates"], 1)
        original = self.evidence.read_bytes()
        with self.assertRaises(ValueError):
            server._import_evidence({"records": [record, {**record, "product_id": "invalid"}]})
        self.assertEqual(self.evidence.read_bytes(), original)
        data = server._dashboard_data()
        candidate = next(row for row in data["candidates"] if row["product_id"] == "cable-sleeve")
        self.assertFalse(candidate["research"]["ready"])
        self.assertNotEqual(candidate["decision"], "TEST")

        record_id = data["evidence"][0]["id"]
        server._exclude_evidence({"id": record_id, "excluded": True})
        self.assertTrue(server._dashboard_data()["evidence"][0]["excluded"])
        server._exclude_evidence({"id": record_id, "excluded": False})
        self.assertFalse(server._dashboard_data()["evidence"][0]["excluded"])

    def test_http_rejects_cross_site_and_nonlocal_hosts(self) -> None:
        http_server = server.ThreadingHTTPServer(("127.0.0.1", 0), server.ResearchHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", http_server.server_port)
            connection.request("POST", "/api/evidence/import", body="{}", headers={"Origin": "https://evil.example"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", http_server.server_port)
            connection.request("GET", "/api/monid/status", headers={"Host": "evil.example"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", http_server.server_port)
            connection.request("GET", "/api/dashboard")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(len(json.loads(response.read())["candidates"]), 9)
            connection.close()
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join()

    def test_failed_provider_result_cannot_be_imported(self) -> None:
        failed = {"product_id": "cable-sleeve", "result": {"status": "COMPLETED", "providerResponse": {"httpStatus": 404}}}
        with patch.object(server.monid, "load_job", return_value=failed):
            with self.assertRaisesRegex(ValueError, "未成功"):
                server._monid_action("preview", {"id": "test"})


if __name__ == "__main__":
    unittest.main()