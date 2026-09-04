"""Turn the report's suggested tests into real files on disk.

The report tells you what tests are missing; this writes them out as runnable
starting points: a Gherkin `.feature` per file and a pytest module with the
generated skeletons. LLM-assisted test generation you can actually commit.
"""
from __future__ import annotations

import os
import re
from typing import Dict

from .schema import Report


def _slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", os.path.splitext(os.path.basename(path))[0].lower()).strip("_")


def emit_tests(report: Report, out_dir: str) -> Dict[str, int]:
    """Write .feature + test_*.py files for every file that has suggested tests."""
    os.makedirs(out_dir, exist_ok=True)
    features = pymods = 0

    for fr in report.files:
        if not fr.suggested_tests:
            continue
        slug = _slug(fr.path)

        scenarios = [t.scenario for t in fr.suggested_tests if t.scenario]
        if scenarios:
            feature = f"Feature: {fr.path}, AI-suggested coverage\n\n" + "\n\n".join(
                s.to_feature() for s in scenarios
            )
            with open(os.path.join(out_dir, f"{slug}.feature"), "w", encoding="utf-8") as fh:
                fh.write(feature + "\n")
            features += 1

        skeletons = [t.pytest_skeleton for t in fr.suggested_tests if t.pytest_skeleton.strip()]
        if skeletons:
            header = f'"""AI-suggested tests for {fr.path}. Review, wire fixtures, then run."""\n\n'
            with open(os.path.join(out_dir, f"test_{slug}.py"), "w", encoding="utf-8") as fh:
                fh.write(header + "\n\n".join(skeletons) + "\n")
            pymods += 1

    return {"features": features, "pytest_modules": pymods}
