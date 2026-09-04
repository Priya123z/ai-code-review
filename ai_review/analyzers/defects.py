"""Defect / risk analyzer.

Versioned prompts live here as module constants  changing review strategy is a
one-file diff, not a hunt through scattered f-strings. Every LLM response is
validated into Pydantic ``Finding`` / ``SuggestedTest`` objects before it can
reach a report.
"""
from __future__ import annotations

from typing import List

from ..core.collector import SourceFile
from ..providers.base import BaseClient
from ..report.schema import (
    Category,
    FileReport,
    Finding,
    GherkinScenario,
    Severity,
    SuggestedTest,
)

PROMPT_VERSION = "defects-v1"

SYSTEM = """You are a senior QA automation engineer and code reviewer.
You review source files and report concrete, high-signal defects and quality risks.
You NEVER invent issues to look thorough  if the code is clean, you say so with an empty findings list.
You always answer with a single JSON object and nothing else."""

USER_TEMPLATE = """Review this {language} file: `{path}`.
{context_block}
Report:
1. `findings`: real defects, bugs, security issues, performance traps, reliability
   or maintainability risks. Each finding needs: title, severity
   (critical|high|medium|low|info), category
   (bug|security|performance|reliability|maintainability|test_gap),
   line (integer or null), detail (why it's a problem), recommendation (the fix),
   confidence (0..1).
2. `suggested_tests`: the most valuable tests that are missing. Each needs:
   title, rationale, a Gherkin `scenario` (name + steps as Given/When/Then
   strings) and a short `pytest_skeleton` string.
3. `summary`: one sentence on the file's overall quality.

Return ONLY JSON of shape:
{{"summary": "...",
  "findings": [{{"title":"","severity":"","category":"","line":null,"detail":"","recommendation":"","confidence":0.8}}],
  "suggested_tests": [{{"title":"","rationale":"","scenario":{{"name":"","steps":["Given ...","When ...","Then ..."]}},"pytest_skeleton":"def test_...():\\n    ..."}}]}}

FILE CONTENT:
```{language}
{content}
```"""


def _coerce_findings(raw: list, path: str) -> List[Finding]:
    out: List[Finding] = []
    for item in raw or []:
        try:
            sev = str(item.get("severity", "medium")).lower()
            cat = str(item.get("category", "bug")).lower()
            out.append(
                Finding(
                    title=item.get("title", "Untitled finding"),
                    severity=Severity(sev) if sev in Severity._value2member_map_ else Severity.medium,
                    category=Category(cat) if cat in Category._value2member_map_ else Category.bug,
                    file=item.get("file", path),
                    line=item.get("line"),
                    detail=item.get("detail", ""),
                    recommendation=item.get("recommendation", ""),
                    confidence=float(item.get("confidence", 0.7) or 0.7),
                )
            )
        except Exception:
            continue  # a single malformed finding never sinks the whole file
    return out


def _coerce_tests(raw: list, path: str) -> List[SuggestedTest]:
    out: List[SuggestedTest] = []
    for item in raw or []:
        try:
            sc = item.get("scenario") or None
            scenario = None
            if isinstance(sc, dict) and sc.get("name"):
                scenario = GherkinScenario(name=sc["name"], steps=list(sc.get("steps", [])))
            out.append(
                SuggestedTest(
                    title=item.get("title", "Suggested test"),
                    rationale=item.get("rationale", ""),
                    target_file=path,
                    scenario=scenario,
                    pytest_skeleton=item.get("pytest_skeleton", ""),
                )
            )
        except Exception:
            continue
    return out


def analyze_file(client: BaseClient, src: SourceFile, repo_context: str = "") -> FileReport:
    context_block = ""
    if repo_context.strip():
        context_block = (
            "\nFor cross-file awareness, here are the other modules in this change "
            "set (signatures only). Use them to catch integration defects, but only "
            "report issues that are actually in the file under review:\n"
            f"```\n{repo_context}\n```\n"
        )
    user = USER_TEMPLATE.format(
        language=src.language, path=src.path, content=src.content, context_block=context_block
    )
    data = client.chat_json(SYSTEM, user)
    findings = _coerce_findings(data.get("findings", []), src.path)
    tests = _coerce_tests(data.get("suggested_tests", []), src.path)
    return FileReport(
        path=src.path,
        language=src.language,
        findings=findings,
        suggested_tests=tests,
        summary=str(data.get("summary", "")).strip(),
    )
