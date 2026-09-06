from __future__ import annotations

import json
import shutil
from pathlib import Path

from sg_product_research.server import _dashboard_data


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
SITE_DIR = ROOT / "_site"


def main() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    shutil.copytree(STATIC_DIR, SITE_DIR)
    index_path = SITE_DIR / "index.html"
    index = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        index.replace('name="app-mode" content="api"', 'name="app-mode" content="static"'),
        encoding="utf-8",
    )
    payload = json.dumps(_dashboard_data(), ensure_ascii=False, indent=2)
    (SITE_DIR / "dashboard-data.json").write_text(payload + "\n", encoding="utf-8")
    (SITE_DIR / ".nojekyll").touch()
    print(f"Built GitHub Pages site in {SITE_DIR}")


if __name__ == "__main__":
    main()