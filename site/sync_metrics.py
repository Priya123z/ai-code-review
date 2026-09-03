"""Rewrite the landing page metrics from the committed report.

The numbers were hardcoded and had drifted from the report they claimed to
describe. CI runs this before publishing so they cannot disagree again.

    python3 site/sync_metrics.py sample-report/report.json site/index.html
"""

import json
import re
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
page = Path(sys.argv[2])

findings = [f for file in report["files"] for f in file["findings"]]
tests = [t for file in report["files"] for t in file["suggested_tests"]]

values = {
    "real findings, latest run": len(findings),
    "critical caught": sum(1 for f in findings if f["severity"] == "critical"),
    "tests generated": len(tests),
    "files, cross-referenced": len(report["files"]),
}

html = page.read_text()

for label, value in values.items():
    pattern = re.compile(
        r'(<div class="metric"><div class="n">)\d+(</div><div class="l">'
        + re.escape(label)
        + r"</div></div>)"
    )
    html, count = pattern.subn(rf"\g<1>{value}\g<2>", html)
    if not count:
        sys.exit(f"could not find the metric labelled {label!r} in {page}")

page.write_text(html)
print("synced:", ", ".join(f"{v} {k}" for k, v in values.items()))
