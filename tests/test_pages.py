from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"


class PagesBuildTests(unittest.TestCase):
    def test_pages_build_contains_read_only_dashboard_data(self) -> None:
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_pages.py")],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads((SITE / "dashboard-data.json").read_text(encoding="utf-8"))
        html = (SITE / "index.html").read_text(encoding="utf-8")
        javascript = (SITE / "app.js").read_text(encoding="utf-8")
        self.assertEqual(len(payload["candidates"]), 9)
        self.assertEqual(payload["lazada_summary"]["sample_size"], 20)
        self.assertIn('href="./styles.css"', html)
        self.assertIn('name="app-mode" content="static"', html)
        self.assertIn('request("./dashboard-data.json")', javascript)
        self.assertTrue((SITE / ".nojekyll").exists())


if __name__ == "__main__":
    unittest.main()