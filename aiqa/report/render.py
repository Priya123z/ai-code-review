"""Render a validated Report into report.json + a self-contained report.html."""
from __future__ import annotations

import json
import os
from typing import Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import Report, Severity

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

SEVERITY_COLORS = {
    "critical": "#ff4d6d",
    "high": "#ff9f45",
    "medium": "#ffd166",
    "low": "#8ac6ff",
    "info": "#9aa4b2",
}


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env


def render_html(report: Report) -> str:
    env = _env()
    template = env.get_template("report.html.j2")
    return template.render(
        r=report,
        breakdown=report.severity_breakdown,
        colors=SEVERITY_COLORS,
        severities=[s.value for s in Severity],
        total_findings=len(report.all_findings),
        total_tests=len(report.all_tests),
    )


def write_report(report: Report, out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "report.json")
    html_path = os.path.join(out_dir, "report.html")
    index_path = os.path.join(out_dir, "index.html")

    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(report.model_dump_json(indent=2))

    html = render_html(report)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    # index.html mirror so a plain directory (GitHub Pages) serves it by default
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return {"json": json_path, "html": html_path, "index": index_path}
