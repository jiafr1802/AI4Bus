import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


SPEC = importlib.util.spec_from_file_location(
    "kalodata_query", Path(__file__).resolve().parents[1] / "scripts" / "kalodata_query.py"
)
QUERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUERY)


class KalodataQueryTests(unittest.TestCase):
    def test_category_spec_uses_sg_and_explicit_level(self):
        args = argparse.Namespace(kind="categories", level=2, category="123", limit=100)
        endpoint, body = QUERY.query_spec(args)
        self.assertEqual(endpoint, "/tiktok/category/rank")
        self.assertEqual(body["region"], "SG")
        self.assertEqual(body["category_ids"], ["123"])
        self.assertEqual(body["category_level"], 2)

    def test_success_is_saved_without_key_and_duplicate_is_blocked(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"success":true,"data":[]}'
        with tempfile.TemporaryDirectory() as directory, patch.object(
            QUERY.urllib.request, "urlopen", return_value=response
        ) as network:
            target, record = QUERY.collect("/tiktok/category/rank", {"region": "SG"}, "secret-test", Path(directory))
            self.assertEqual(record["status"], "success")
            self.assertNotIn("secret-test", target.read_text())
            self.assertEqual(network.call_args[0][0].get_header("Connection"), "close")
            with self.assertRaises(FileExistsError):
                QUERY.collect("/tiktok/category/rank", {"region": "SG"}, "secret-test", Path(directory))
            self.assertEqual(network.call_count, 1)

    def test_attempt_limit_blocks_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(QUERY.urllib.request, "urlopen") as network:
            for index in range(10):
                (Path(directory) / f"{index}.json").write_text("{}")
            with self.assertRaises(ValueError):
                QUERY.collect("/tiktok/category/rank", {}, "secret-test", Path(directory))
            network.assert_not_called()

    def test_failed_responses_are_saved_as_unknown_without_retry(self):
        for failure in (TimeoutError(), QUERY.http.client.IncompleteRead(b"partial")):
            response = MagicMock()
            response.__enter__.return_value.read.side_effect = failure
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory, patch.object(
                QUERY.urllib.request, "urlopen", return_value=response
            ) as network:
                target, record = QUERY.collect("/tiktok/product/rank", {}, "secret-test", Path(directory))
                self.assertIn("response unavailable", record["status"])
                self.assertEqual(network.call_count, 1)
                self.assertIsNone(json.loads(target.read_text())["actual_credits"])

    def test_round_budget_counts_failed_attempts_and_locks_limits(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            QUERY.urllib.request, "urlopen", side_effect=TimeoutError()
        ) as network:
            QUERY.collect("/tiktok/product/comments", {"product_id": "one"}, "secret-test", Path(directory), 40, 0.02)
            with self.assertRaises(ValueError):
                QUERY.collect("/tiktok/product/comments", {"product_id": "two"}, "secret-test", Path(directory), 40, 0.03)
            QUERY.collect("/tiktok/product/comments", {"product_id": "two"}, "secret-test", Path(directory), 40, 0.02)
            with self.assertRaises(ValueError):
                QUERY.collect("/tiktok/product/comments", {"product_id": "three"}, "secret-test", Path(directory), 40, 0.02)
            self.assertEqual(network.call_count, 2)

    def test_response_redacts_echoed_key(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"success":false,"message":"secret-test rejected"}'
        with tempfile.TemporaryDirectory() as directory, patch.object(
            QUERY.urllib.request, "urlopen", return_value=response
        ):
            target, record = QUERY.collect("/tiktok/product/images", {}, "secret-test", Path(directory))
            self.assertNotIn("secret-test", target.read_text())
            self.assertIn("[REDACTED]", record["response"]["message"])


if __name__ == "__main__":
    unittest.main()