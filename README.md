# ai-code-review

Reads your changed files with an LLM and tells you what is likely to break, which
tests are missing, and how to fix a Playwright locator that stopped matching.

Runs two ways: a CLI, and a GitHub Action that reviews a pull request's diff.

[**Sample report**](https://priya123z.github.io/ai-code-review/report/) ·
[try the same three prompts in a browser](https://priya123z.github.io/#demos), no install and no key

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
  what you changed, so the boring findings (a mutable default, an unguarded
  division, a missing negative-path test) are already written down before a
  human spends attention on them.
  [Pull request #1](https://github.com/Priya123z/ai-code-review/pull/1) is that
  claim as a worked example: a branch adding a coupon module, the comment the
  reviewer left on it, and the
  [report it produced](https://priya123z.github.io/ai-code-review/report/pr/).
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

Where **not** to use it: as the review. It has no idea what your product is
supposed to do, so it cannot tell you a feature is wrong, only that a line of
code is likely to behave badly. Treat it as the pass that happens before the
one that matters.

## What it does

| | |
|---|---|
| **Finds defects** | Severity, category, line, why it matters, and a suggested fix |
| **Writes the missing tests** | Gherkin scenarios and pytest skeletons, emitted as real files |
| **Repairs locators** | A selector that no longer matches, plus the current markup, in; a working Playwright locator out |
| **Gates the build** | Weighted risk score with configurable critical and high thresholds |
| **Reads siblings** | Function and class signatures from neighbouring files, so cross-file mistakes are visible |

## Quick start

```bash
pip install -e ".[dev]"                # dev adds pytest, so the suite runs too

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

With `diff: "true"` on a `pull_request` trigger, the scan is scoped to the files
the branch touched and the findings are posted as a single comment, edited in
place on each push rather than appended. A branch that changes no reviewable
source is reported as having nothing to review, and no model call is made: a bot
that answers "0 findings" when it never looked is worse than one that says so.

This repository runs itself that way, and
[`.github/workflows/code-review.yml`](.github/workflows/code-review.yml) is the
working copy. [#1](https://github.com/Priya123z/ai-code-review/pull/1) is a live
one: three findings on the one file that branch touched.

### Where the reports go

Each run uploads the HTML report as a workflow artifact named
`code-review-report`, found at the bottom of the run summary page, or with
`gh run download <run-id> -n code-review-report`. Artifacts expire after 14 days
and need a signed-in account, so two reports are also committed and published,
which is what the links point at:

| | |
|---|---|
| [/report/](https://priya123z.github.io/ai-code-review/report/) | `sample-report/`, the whole demo module: 3 files, 16 findings, risk 483 |
| [/report/pr/](https://priya123z.github.io/ai-code-review/report/pr/) | `pr-report/`, the diff-scoped review from [#1](https://github.com/Priya123z/ai-code-review/pull/1): the one file that branch touched |

### How stable this is

Both published copies are snapshots of one run, not live output. `pr-report/` is
[run 34113957852](https://github.com/Priya123z/ai-code-review/actions/runs/34113957852),
so it will not always match the comment currently on #1, and that is worth being
precise about rather than glossing.

Scanning the same unchanged diff repeatedly:

| | |
|---|---|
| stable | the mutable default, the unguarded division, and the `max()` on a possibly-empty sequence. Every run flags all three |
| unstable | a fourth finding, about unvalidated percent values, appears in some runs and not others |
| unstable | the grading. The same three defects have come back anywhere from medium to critical |

So what it finds is reproducible and how it ranks what it finds is not. Two runs
over identical code have scored `risk 250` with two criticals and `risk 120`
with none. The published copy is one of the `risk 120` runs: the same three
defects, all graded high.

That is the reason `--fail-on-gate` is off in this repository's own workflow.
Pointed at `--max-critical 0`, that same unchanged file would have failed the
first run and passed the second. Use it as a list of things to look at; gate on
it only once you have watched what it flags on your code for a while.

## Running on a free tier

Groq's free tier allows 30 requests a minute, 1000 a day, 8000 tokens a minute
and 200k a day. Tokens per minute is what binds: a couple of 2000-token reviews
exhaust the minute long before they get near 30 requests.

So there is a chain rather than one provider and hope. Groq is tried first, then
its own smaller models, then OpenRouter. Two OpenRouter free models returned 429
on the very first call while this was being written, which is why the fallback
goes sideways as well as down.

**It will not tell you your code is fine when it could not read it.** A provider
outage used to produce zero findings and a passing gate, which is
indistinguishable from clean code. Files that fail now carry an error, the report
says so instead of "no defects flagged", the gate fails if nothing was reviewed,
and the CLI exits `2`.

## Configuration

| Variable | Default | |
|---|---|---|
| `GROQ_API_KEY` | none | Primary provider |
| `OPENROUTER_API_KEY` | none | Fallback |
| `AI_REVIEW_MODEL` | provider default | Overridden by `--model` |
| `AI_REVIEW_MAX_FILES` | `12` | Cap per run |
| `AI_REVIEW_MAX_CRITICAL` | `0` | Gate threshold |
| `AI_REVIEW_MAX_HIGH` | `3` | Gate threshold |

## Layout

```
ai_review/
  cli.py        argparse entry point
  core/         config, collector, pipeline
  providers/    base, groq, openrouter, chain     the only code that does HTTP
  analyzers/    defects, selfheal, context        prompts live here
  report/       schema, render, emit
  templates/    report.html.j2
action.yml      the composite GitHub Action
examples/       flask_shop, the deliberately buggy module the demo scans
sample-report/  a committed run over that module, published at /report/
pr-report/      a committed run over pull request #1, published at /report/pr/
site/           the landing page, published alongside both reports
tests/          32 tests, no API key needed
```

A report is a plain dict, built by the functions in `report/schema.py`. What the
pipeline assembles, what lands in `report.json` and what the template renders are
all the same shape, so there is nothing to keep in sync and nothing to serialise.
The five derived numbers, risk score included, are written into the dict, which
is how CI thresholds on the file without importing this package.

The LLM is reachable only through one `chat(system, user, as_json)` method. That
is what lets the whole suite run offline: tests substitute that one method and
nothing above it knows the difference. There is a test asserting `chat_json`
still routes through it, because breaking that silently bypassed every fake in
the suite once already.

## Tests

```bash
pytest -q          # 32 passed, no API key required
```

Covers the provider chain falling through and exhausting, model precedence
between `--model` and the environment, JSON extraction from fenced and prose
responses, the gate refusing to pass a run that reviewed nothing, malformed
model output being dropped without sinking the rest of the file, and the
context, heal and emit capabilities.

## Honest limitations

- Findings are suggestions. Some are wrong, and confidence is not calibrated.
- Python only for now; the collector filters on `.py`.
- Sibling context is regex-extracted signatures, not a real index. It catches
  obvious mismatches, not deep call-graph problems.
- Two runs on the same file can differ. That is the nature of it, which is why
  the tests assert on properties rather than on exact output. [How stable this
  is](#how-stable-this-is) measures it on one unchanged diff: the defects
  repeated, the severities did not.

MIT.
