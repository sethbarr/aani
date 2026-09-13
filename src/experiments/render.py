"""Render a portable planner with embedded data, scripts and downloadable artifacts."""

import json
from pathlib import Path


def render_viewer(plan: dict, output: Path) -> None:
    """Embed artifacts so opening the HTML never depends on sibling download links."""
    names = ("opentrons_water_demo.py", "simulation_report.json", "gerardo_brief.md")
    files = {name: (output / name).read_text(encoding="utf-8") for name in names}
    payload = json.dumps({"plan": plan, "files": files}, ensure_ascii=False)
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    root = Path(__file__).parent
    template = (root / "viewer.template.html").read_text(encoding="utf-8")
    script = (root / "browser_planner.js").read_text(encoding="utf-8")
    page = template.replace("__PLAN_DATA__", payload).replace("__PLANNER_SCRIPT__", script)
    (output / "index.html").write_text(page, encoding="utf-8")
