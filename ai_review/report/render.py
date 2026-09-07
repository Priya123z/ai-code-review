"""Render a report into report.json and a self-contained index.html."""
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import schema

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

SEVERITY_COLORS = {
    "critical": "#ff4d6d",
    "high": "#ff9f45",
    "medium": "#ffd166",
    "low": "#8ac6ff",
    "info": "#9aa4b2",
}


def render_html(report, max_critical=0, max_high=3):
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template("report.html.j2").render(
        r=report,
        breakdown=report["severity_breakdown"],
        colors=SEVERITY_COLORS,
        severities=schema.SEVERITIES,
        gate_failed=schema.gate_fails(report, max_critical, max_high),
        total_findings=len(schema.all_findings(report)),
        total_tests=len(schema.all_tests(report)),
    )


def write_report(report, out_dir, max_critical=0, max_high=3):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "report.json")
    # index.html rather than report.html: a plain directory server, GitHub Pages
    # included, serves it without being told to. There used to be both, byte for
    # byte identical.
    index_path = os.path.join(out_dir, "index.html")

    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(schema.to_json(report))
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(report, max_critical, max_high))

    return {"json": json_path, "html": index_path}
