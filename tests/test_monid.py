from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sg_product_research import monid


DETAILS = {"price": {"type": "PER_RESULT", "amount": {"value": 0.01, "currency": "USD"}},
           "input": {"body": {"properties": {"maxItems": {"type": "integer"}}}}}


class MonidTests(unittest.TestCase):
    def test_estimate_respects_result_limit_and_single_query(self):
        self.assertEqual(str(monid.estimate_cost(DETAILS, {"maxItems": 5, "queries": ["cable"]})), "0.05")
        for inputs in ({}, {"maxItems": 11}, {"maxItems": True}, {"maxItems": 5, "queries": ["a", "b"]}):
            with self.assertRaises(monid.MonidError):
                monid.estimate_cost(DETAILS, inputs)

    def test_unknown_price_is_not_executed(self):
        with self.assertRaises(monid.MonidError):
            monid.estimate_cost({"price": {"type": "METERED", "amount": {"value": 0.1, "currency": "USD"}}}, {})

    def test_missing_key_never_sends_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(monid, "build_opener") as opener:
            with self.assertRaises(monid.MonidError):
                monid.discover("amazon reviews")
            opener.assert_not_called()

    def test_prepare_is_free_and_execute_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(monid, "RUNS_DIR", Path(temporary)), \
                patch.object(monid, "_request", return_value=DETAILS) as request, \
                patch.dict(os.environ, {"MONID_ENABLE_RUNS": "1", "MONID_WORKSPACE_CAP_CONFIRMED": "1"}):
            job = monid.prepare({"product_id": "cable-sleeve", "provider": "apify", "endpoint": "/example", "input": {"maxItems": 5}})
            self.assertEqual(request.call_args.args[0], "/inspect")
            with self.assertRaises(monid.MonidError):
                monid.execute(job["id"], False)
            request.side_effect = [DETAILS, {"runId": "remote", "status": "READY"}]
            result = monid.execute(job["id"], True)
            self.assertEqual(result["status"], "READY")
            with self.assertRaises(monid.MonidError):
                monid.execute(job["id"], True)
            self.assertEqual(request.call_count, 3)

    def test_timeout_leaves_unknown_job_without_automatic_retry(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(monid, "RUNS_DIR", Path(temporary)), \
                patch.object(monid, "_request", side_effect=[DETAILS, DETAILS, monid.MonidError("timeout")]) as request, \
                patch.dict(os.environ, {"MONID_ENABLE_RUNS": "1", "MONID_WORKSPACE_CAP_CONFIRMED": "1"}):
            job = monid.prepare({"product_id": "cable-sleeve", "provider": "apify", "endpoint": "/example", "input": {"maxItems": 5}})
            with self.assertRaises(monid.MonidError):
                monid.execute(job["id"], True)
            self.assertEqual(monid.load_job(job["id"])["status"], "UNKNOWN")
            with self.assertRaises(monid.MonidError):
                monid.execute(job["id"], True)
            self.assertEqual(request.call_count, 3)


if __name__ == "__main__":
    unittest.main()