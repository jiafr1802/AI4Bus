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
        self.assertIn('id="research-candidate"', html)
        self.assertIn('id="guide-method"', html)
        self.assertIn('id="guide-workflow"', html)
        self.assertIn('id="model-origin"', html)
        self.assertIn("项目自定的启发式评分", html)
        self.assertIn("它不是净利润", html)
        self.assertIn('id="project-todo"', html)
        self.assertIn("当前卡点 / Todo", html)
        self.assertIn("本次核对：9 个候选中仅 1 个有原始样本", html)
        self.assertIn("不是实时账号状态", html)
        self.assertIn("GitHub Pages 是发布时的数据快照", html)
        self.assertIn("费用预估不是账单硬限额", html)
        self.assertGreaterEqual(len(payload["evidence"]), 40)
        self.assertIn("research", payload["candidates"][0])
        self.assertEqual(payload["lazada_summary"]["sampled_at"], "2026-09-06")
        self.assertNotIn("jobs", payload)
        self.assertNotIn("monid", payload)
        self.assertTrue((SITE / ".nojekyll").exists())


if __name__ == "__main__":
    unittest.main()