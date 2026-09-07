"""Defect / risk analyzer.

Versioned prompts live here as module constants, so changing review strategy is
a one-file diff rather than a hunt through scattered f-strings. Everything the
model returns goes through the builders in report/schema.py, which normalise it.
"""
from ..report import schema

PROMPT_VERSION = "defects-v1"

SYSTEM = """You are a senior QA automation engineer and code reviewer.
You review source files and report concrete, high-signal defects and quality risks.
You NEVER invent issues to look thorough. If the code is clean, you say so with an empty findings list.
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


def _findings_from(raw, path):
    out = []
    for item in raw or []:
        # A finding with neither a title nor a detail says nothing, and models do
        # occasionally emit one. Dropping it here keeps the rest of the file.
        if not isinstance(item, dict) or not (item.get("title") or item.get("detail")):
            continue
        try:
            out.append(schema.finding(
                title=item.get("title", "Untitled finding"),
                severity=item.get("severity", "medium"),
                category=item.get("category", "bug"),
                file=item.get("file", path),
                line=item.get("line"),
                detail=item.get("detail", ""),
                recommendation=item.get("recommendation", ""),
                confidence=item.get("confidence", 0.7),
            ))
        except Exception:
            continue  # a single malformed finding never sinks the whole file
    return out


def _tests_from(raw, path):
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        try:
            sc = item.get("scenario")
            out.append(schema.suggested_test(
                title=item.get("title", "Suggested test"),
                rationale=item.get("rationale", ""),
                target_file=path,
                scenario=(schema.scenario(sc["name"], sc.get("steps"))
                          if isinstance(sc, dict) and sc.get("name") else None),
                pytest_skeleton=item.get("pytest_skeleton", ""),
            ))
        except Exception:
            continue
    return out


def analyze_file(client, src, repo_context=""):
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
    return schema.file_report(
        path=src.path,
        language=src.language,
        findings=_findings_from(data.get("findings", []), src.path),
        suggested_tests=_tests_from(data.get("suggested_tests", []), src.path),
        summary=data.get("summary", ""),
    )
