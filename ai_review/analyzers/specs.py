"""Turn a written requirement into Gherkin scenarios and pytest skeletons.

Separate from defects.py because the input is prose, not code: there is no file,
no line numbers and nothing to gate on. It is the same JSON-in-JSON-out shape.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..providers.base import BaseClient
from ..report.schema import GherkinScenario

PROMPT_VERSION = "specs-v1"

SYSTEM = """You are a senior QA engineer writing test cases from a requirement.

Cover the happy path, the boundaries, and the ways this realistically breaks 
invalid input, permissions, concurrency, and anything the requirement leaves
unsaid. Do not pad the list to look thorough.

Answer with a single JSON object and nothing else:
{
  "feature": "short feature name",
  "scenarios": [
    {"name": "...", "tags": ["smoke"], "steps": ["Given ...", "When ...", "Then ..."]}
  ],
  "pytest_cases": [
    {"function_name": "test_...", "intent": "one line", "skeleton": "def test_...():\\n    ..."}
  ],
  "coverage_notes": "what a reviewer should still check by hand"
}"""

USER_TEMPLATE = """Requirement:

{story}

Write between 3 and 8 scenarios. Steps must start with Given, When, Then, And or But."""


class PytestCase(BaseModel):
    function_name: str = "test_case"
    intent: str = ""
    skeleton: str = ""


class SpecSuite(BaseModel):
    feature: str = "Feature"
    scenarios: List[GherkinScenario] = Field(default_factory=list)
    pytest_cases: List[PytestCase] = Field(default_factory=list)
    coverage_notes: str = ""

    def to_feature_file(self) -> str:
        body = "\n\n".join(s.to_feature() for s in self.scenarios)
        return f"Feature: {self.feature}\n\n{body}\n"

    def to_pytest_file(self) -> str:
        header = '"""Generated from a requirement. Review before relying on these."""\n\nimport pytest\n\n'
        blocks = []
        for case in self.pytest_cases:
            skeleton = case.skeleton.strip() or f"def {case.function_name}():\n    pass"
            blocks.append(f"# {case.intent}\n{skeleton}" if case.intent else skeleton)
        return header + "\n\n\n".join(blocks) + "\n"


def generate_specs(client: BaseClient, story: str) -> SpecSuite:
    raw = client.chat_json(SYSTEM, USER_TEMPLATE.format(story=story.strip()))

    scenarios = []
    for item in raw.get("scenarios") or []:
        try:
            scenarios.append(GherkinScenario(**item))
        except Exception:
            continue

    cases = []
    for item in raw.get("pytest_cases") or []:
        try:
            cases.append(PytestCase(**item))
        except Exception:
            continue

    return SpecSuite(
        feature=str(raw.get("feature") or "Feature")[:120],
        scenarios=scenarios,
        pytest_cases=cases,
        coverage_notes=str(raw.get("coverage_notes") or ""),
    )
