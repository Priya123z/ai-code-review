from ai_review.report import schema


def _finding(sev):
    return schema.finding(title="x issue", severity=sev, category="bug", file="a.py", detail="d")


def _report(*severities, **kw):
    return schema.report(files=[schema.file_report(path="a.py",
                                                   findings=[_finding(s) for s in severities])], **kw)


def test_severity_weights_are_ordered():
    w = schema.SEVERITY_WEIGHT
    assert w["critical"] > w["high"] > w["medium"] > w["low"] > w["info"]


def test_risk_score_and_breakdown():
    r = _report("critical", "high")
    assert r["risk_score"] == schema.SEVERITY_WEIGHT["critical"] + schema.SEVERITY_WEIGHT["high"]
    assert r["severity_breakdown"]["critical"] == 1
    assert r["severity_breakdown"]["high"] == 1
    assert len(schema.all_findings(r)) == 2


def test_gate_thresholds():
    r = _report("critical")
    assert schema.gate_fails(r, max_critical=0, max_high=3) is True
    assert schema.gate_fails(r, max_critical=1, max_high=3) is False


def test_gate_fails_when_nothing_could_be_reviewed():
    # A provider outage produces no findings, which is indistinguishable from
    # clean code unless the gate looks at what was actually read.
    r = schema.report(files=[schema.file_report(path="a.py", error="429 from every provider")])
    assert r["reviewed_count"] == 0
    assert r["incomplete"] is True
    assert schema.gate_fails(r) is True


def test_out_of_range_confidence_is_clamped_not_raised():
    # The analyzer drops any finding that raises, so rejecting one outright loses
    # it silently. Clamping keeps the finding and the number stays meaningful.
    assert _finding("low") and schema.finding("t", "low", "bug", "a.py", confidence=5)["confidence"] == 1.0
    assert schema.finding("t", "low", "bug", "a.py", confidence=-2)["confidence"] == 0.0
    assert schema.finding("t", "low", "bug", "a.py", confidence="nonsense")["confidence"] == 0.7


def test_unknown_severity_and_category_fall_back():
    f = schema.finding("t", "Catastrophic", "vibes", "a.py")
    assert f["severity"] == "medium"
    assert f["category"] == "bug"


def test_report_survives_a_json_round_trip():
    import json
    r = schema.report(project="demo", files=[schema.file_report("a.py", findings=[_finding("medium")])])
    restored = json.loads(schema.to_json(r))
    assert restored["project"] == "demo"
    assert restored["files"][0]["findings"][0]["severity"] == "medium"
    assert restored["risk_score"] == schema.SEVERITY_WEIGHT["medium"]
