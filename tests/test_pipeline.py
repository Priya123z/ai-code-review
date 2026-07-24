import os

from aiqa.core.config import Config
from aiqa.core.pipeline import run, run_and_write
from aiqa.report.render import render_html

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "shopping_cart")


def test_pipeline_runs_with_fake_client(fake_client):
    cfg = Config(target=EXAMPLE, max_files=5)
    report = run(cfg, client=fake_client)
    assert report.files, "should have analyzed at least one file"
    assert len(report.all_findings) >= 1
    assert report.risk_score > 0


def test_run_and_write_creates_artifacts(fake_client, tmp_path):
    cfg = Config(target=EXAMPLE, out_dir=str(tmp_path), max_files=3)
    report, paths = run_and_write(cfg, client=fake_client)
    for key in ("json", "html", "index"):
        assert os.path.exists(paths[key])
    html = open(paths["html"], encoding="utf-8").read()
    assert "AI QA Pipeline Report" in html
    assert "Division by zero" in html


def test_render_html_contains_gate_and_findings(fake_client):
    cfg = Config(target=EXAMPLE, max_files=2)
    report = run(cfg, client=fake_client)
    html = render_html(report)
    assert "QUALITY GATE" in html
    assert "Suggested tests" in html


def test_analyzer_survives_malformed_finding():
    from tests.conftest import FakeClient
    bad = {"summary": "s", "findings": [{"nonsense": True}, {"title": "valid finding", "severity": "low",
           "category": "bug", "detail": "a real detail"}], "suggested_tests": []}
    client = FakeClient(payload=bad)
    cfg = Config(target=EXAMPLE, max_files=1)
    report = run(cfg, client=client)
    # the malformed finding is dropped, the valid one survives
    titles = [f.title for f in report.all_findings]
    assert "valid finding" in titles
    assert len(titles) == 1
