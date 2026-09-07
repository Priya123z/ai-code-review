"""What a report is made of, and the numbers a CI gate reads off one.

Reports are plain dicts. What the pipeline builds, what lands in report.json and
what the template renders are all the same shape, so there is nothing to keep in
sync and nothing to serialise. The builders below normalise as they go, because
a model that returns "severity": "Critical!" or a confidence of 5 should produce
a usable finding rather than an exception three layers up.
"""
import json
from datetime import datetime, timezone

# Order matters: the report's severity bar and legend are drawn in this order.
SEVERITIES = ["critical", "high", "medium", "low", "info"]

# What a finding of each severity adds to the risk score. Deliberately steep:
# one critical outweighs any number of lows, because that is how a gate should
# behave.
SEVERITY_WEIGHT = {"critical": 100, "high": 40, "medium": 10, "low": 3, "info": 1}

CATEGORIES = ["bug", "security", "performance", "reliability", "maintainability", "test_gap"]


def finding(title, severity, category, file, line=None, detail="",
            recommendation="", confidence=0.7):
    severity = str(severity or "").strip().lower()
    category = str(category or "").strip().lower()
    try:
        line = int(line)
        line = line if line >= 1 else None
    except (TypeError, ValueError):
        line = None
    try:
        confidence = min(1.0, max(0.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.7
    return {
        "title": str(title).strip()[:160] or "Untitled finding",
        "severity": severity if severity in SEVERITY_WEIGHT else "medium",
        "category": category if category in CATEGORIES else "bug",
        "file": file,
        "line": line,
        "detail": str(detail).strip(),
        "recommendation": str(recommendation).strip(),
        "confidence": confidence,
    }


def scenario(name, steps):
    return {"name": str(name).strip(), "steps": [str(s) for s in steps or []]}


def scenario_to_feature(sc):
    body = "\n".join(f"    {s}" for s in sc["steps"])
    return f"  Scenario: {sc['name']}\n{body}"


def suggested_test(title, rationale="", target_file="", scenario=None, pytest_skeleton=""):
    return {
        "title": str(title).strip() or "Suggested test",
        "rationale": str(rationale).strip(),
        "target_file": target_file,
        "scenario": scenario,
        "pytest_skeleton": pytest_skeleton or "",
    }


def file_report(path, language="python", findings=None, suggested_tests=None,
                summary="", error=""):
    return {
        "path": path,
        "language": language,
        "findings": findings or [],
        "suggested_tests": suggested_tests or [],
        "summary": str(summary).strip(),
        # Set when the file could not be reviewed at all. Without it a provider
        # outage looked identical to a clean file: no findings, gate passes.
        "error": error,
    }


def report(project="unknown", model="unknown", commit="", files=None, notes=""):
    """Assemble the top-level artifact, derived numbers included.

    The five derived values are written into the dict rather than computed on
    read, so report.json carries them and CI can threshold on the file without
    importing this package.
    """
    files = files or []
    findings = all_findings({"files": files})
    failed = [f for f in files if f["error"]]
    return {
        "project": project,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "files": files,
        "notes": notes,
        "risk_score": sum(SEVERITY_WEIGHT[f["severity"]] for f in findings),
        "severity_breakdown": {s: sum(1 for f in findings if f["severity"] == s)
                               for s in SEVERITIES},
        "reviewed_count": len(files) - len(failed),
        "failed_count": len(failed),
        "incomplete": bool(failed),
    }


def all_findings(rep):
    return [f for fr in rep["files"] for f in fr["findings"]]


def all_tests(rep):
    return [t for fr in rep["files"] for t in fr["suggested_tests"]]


def failed_files(rep):
    return [fr for fr in rep["files"] if fr["error"]]


def gate_fails(rep, max_critical=0, max_high=3):
    # An incomplete run cannot claim the code is clean.
    if rep["files"] and rep["reviewed_count"] == 0:
        return True
    b = rep["severity_breakdown"]
    return b["critical"] > max_critical or b["high"] > max_high


def to_json(rep):
    return json.dumps(rep, indent=2)
