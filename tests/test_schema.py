import pytest
from pydantic import ValidationError

from ai_review.report.schema import (
    Category,
    FileReport,
    Finding,
    Report,
    Severity,
)


def _finding(sev):
    return Finding(title="x issue", severity=sev, category=Category.bug, file="a.py", detail="d")


def test_severity_weight_order():
    assert Severity.critical.weight > Severity.high.weight > Severity.medium.weight
    assert Severity.low.weight > Severity.info.weight


def test_risk_score_and_breakdown():
    r = Report(files=[FileReport(path="a.py", findings=[_finding(Severity.critical), _finding(Severity.high)])])
    assert r.risk_score == Severity.critical.weight + Severity.high.weight
    assert r.severity_breakdown["critical"] == 1
    assert r.severity_breakdown["high"] == 1
    assert len(r.all_findings) == 2


def test_gate_logic():
    r = Report(files=[FileReport(path="a.py", findings=[_finding(Severity.critical)])])
    assert r.gate_fails(max_critical=0, max_high=3) is True
    assert r.gate_fails(max_critical=1, max_high=3) is False


def test_invalid_confidence_rejected():
    with pytest.raises(ValidationError):
        Finding(title="bad", severity=Severity.low, category=Category.bug, file="a.py", detail="d", confidence=5)


def test_report_round_trips_json():
    r = Report(project="demo", files=[FileReport(path="a.py", findings=[_finding(Severity.medium)])])
    restored = Report.model_validate_json(r.model_dump_json())
    assert restored.project == "demo"
    assert restored.all_findings[0].severity == Severity.medium
