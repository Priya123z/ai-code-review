# ai-code-review

Reads your changed files with an LLM and tells you what is likely to break, which
tests are missing, and how to fix a Playwright locator that stopped matching.

Runs three ways: a CLI, a GitHub Action, and an HTTP API.

[**Try it in a browser**](https://priya123z.github.io/#demos) — runs on your own free key, no install ·
[Sample report](https://priya123z.github.io/ai-code-review/report/)

[![Tests](https://github.com/Priya123z/ai-code-review/actions/workflows/tests.yml/badge.svg)](https://github.com/Priya123z/ai-code-review/actions/workflows/tests.yml)
[![Review](https://github.com/Priya123z/ai-code-review/actions/workflows/code-review.yml/badge.svg)](https://github.com/Priya123z/ai-code-review/actions/workflows/code-review.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Why

A linter tells you `total / len(items)` is valid Python. It cannot tell you that
`items` is empty whenever a cart is new, that the test suite never covers that
path, and that the fix belongs in `__init__` rather than at the call site. That
gap between "syntactically fine" and "will page someone at 2am" is what this
looks at.

It is not a replacement for review. It is a first pass that arrives before the
human one, with the boring findings already written down.

## When you would reach for this

- **Before you open a pull request.** `ai-review scan . --diff` looks only at
  what you changed. The point is that the boring findings — mutable default,
  unguarded division, a missing negative-path test — are already written down
  before a human spends attention on them.
- **On a repository nobody has reviewed in a year.** Run it over a directory and
  read the report as a triage list. It is unusually good at spotting where tests
  do not exist, because that is a structural question rather than a judgement
  one.
- **When a Playwright suite starts failing after a frontend redesign.**
  `ai-review heal` takes the selector that stopped matching plus the current
  markup and gives you a locator that works, preferring role and label over CSS.
  Faster than opening devtools for the twelfth time.
- **As a gate on a repo where nobody reviews test coverage.**
  `--fail-on-gate` fails the build over a configurable count of critical and
  high findings. Start with it off and watch what it flags for a week first.
- **As a shared service for a team.** `server/` is the same three capabilities
  over HTTP, so one instance answers for everyone rather than each person
  installing a CLI and finding their own key.

Where **not** to use it: as the review. It has no idea what your product is
supposed to do, so it cannot tell you a feature is wrong — only that a line of
code is likely to behave badly. Treat it as the pass that happens before the
one that matters.

## What it does

| | |
|---|---|
| **Finds defects** | Severity, category, line, why it matters, and a suggested fix |
| **Writes the missing tests** | Gherkin scenarios and pytest skeletons, emitted as real files |
| **Repairs locators** | A selector that no longer matches plus the current markup, in, a working Playwright locator out |
| **Gates the build** | Weighted risk score with configurable critical and high thresholds |
| **Reads siblings** | Function and class signatures from neighbouring files, so cross-file mistakes are visible |

## Quick start

```bash
pip install -e .

export GROQ_API_KEY=gsk_...            # free key: console.groq.com/keys
ai-review scan ./src --out report/
open report/index.html
```

Other commands:

```bash
ai-review scan . --diff --fail-on-gate         # only what changed, fail the build
ai-review scan ./src --emit-tests tests/gen/   # write the suggested tests out
ai-review gen-tests ./src --out tests/gen/
ai-review heal --selector "#pay-now" --html page.html
```

## As a GitHub Action

```yaml
- uses: Priya123z/ai-code-review@main
  with:
    target: .
    diff: "true"
    fail-on-gate: "false"
  env:
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

## As an API

`server/` is a FastAPI app exposing the same three capabilities over HTTP, for
when you want one instance shared across a team rather than everyone running the
CLI.

It is not currently deployed anywhere. Hugging Face made Docker Spaces a paid
feature partway through building this, and rather than pay for a demo, the
portfolio now calls Groq straight from the browser with whatever key the visitor
supplies — Groq allows cross-origin requests, so no server is needed for that.
The service is still here, still tested, and `server/deploy-space.sh` will push
it to a Space if you have PRO, or the Dockerfile will run anywhere.

```bash
pip install -r server/requirements.txt
uvicorn server.app:app --port 8000
```

```
POST /api/review   { code, filename }        → defects + suggested tests
POST /api/specs    { story }                 → Gherkin + pytest
POST /api/heal     { selector, html }        → a locator that works
GET  /api/health                             → configured providers
GET  /api/quota                              → what is left of today's budget
```

Run it locally with the commands above, or build the image:

```bash
docker build -f server/Dockerfile -t ai-review-api .
docker run -p 7860:7860 -e GROQ_API_KEY=gsk_... ai-review-api
```

`./server/deploy-space.sh <hf-username>` pushes it to a Hugging Face Space, which
needs a PRO subscription for Docker SDK spaces.

## Running on a free tier

This is most of the engineering, so it is worth being explicit.

Groq's free tier allows 30 requests a minute, 1000 a day, 8000 tokens a minute
and 200k a day. **Tokens per minute is what binds** — a couple of 2000-token
reviews exhaust the minute long before they get near 30 requests. So the budget
is counted in tokens, and a request is refused before it is sent rather than
after a 429 comes back.

Providers are tried in order: Groq, then OpenRouter, then a saved response. Two
OpenRouter free models returned 429 on the very first call while this was being
written, which is why there is a chain at all rather than one provider and hope.

When the budget is spent the API answers `200` with a pre-generated example
labelled `"source": "cached"`. It does not pretend to be live, and it does not
return a 500 — a dead demo teaches a visitor nothing. Anyone who wants unlimited
runs sends their own key in `X-API-Key` and skips the budget entirely.

**It will not tell you your code is fine when it could not read it.** A provider
outage used to produce zero findings and a passing gate, which is
indistinguishable from clean code. Files that fail now carry an error, the gate
fails if nothing was reviewed, and the CLI exits `2`.

## Configuration

| Variable | Default | |
|---|---|---|
| `GROQ_API_KEY` | — | Primary provider |
| `OPENROUTER_API_KEY` | — | Fallback |
| `AI_REVIEW_MODEL` | provider default | Overridden by `--model` |
| `AI_REVIEW_MAX_FILES` | `12` | Cap per run |
| `AI_REVIEW_MAX_CRITICAL` | `0` | Gate threshold |
| `AI_REVIEW_MAX_HIGH` | `3` | Gate threshold |
| `ALLOWED_ORIGINS` | the portfolio origin | CORS, server only |

## Layout

```
ai_review/
  cli.py                  argparse entry point
  core/       config, collector, pipeline
  providers/  base, groq, openrouter, chain      the only code that does HTTP
  analyzers/  defects, specs, selfheal, context  prompts live here
  report/     schema, render, emit               Pydantic contracts
  templates/  report.html.j2
server/       app, quota, cache, samples, Dockerfile
tests/        45 tests, no API key needed
```

The LLM is reachable only through one `chat(system, user, as_json)` method. That
is what lets the whole suite run offline: tests substitute that one method and
nothing above it knows the difference. There is a test asserting `chat_json`
still routes through it, because breaking that silently bypassed every fake in
the suite once already.

## Tests

```bash
pip install -e ".[dev]"
pytest -q          # 45 passed, no API key required
# last local run: 45 passed
```

Covers the provider chain falling through and exhausting, quota refusal and
per-visitor limits, the cached fallback, own-key bypass, input truncation, and
malformed model output being dropped without sinking the rest of the file.

## Honest limitations

- Findings are suggestions. Some are wrong, and confidence is not calibrated.
- Python only for now; the collector filters on `.py`.
- Sibling context is regex-extracted signatures, not a real index. It catches
  obvious mismatches, not deep call-graph problems.
- Two runs on the same file can differ. That is the nature of it, which is why
  the tests assert on properties rather than on exact output.

MIT.
