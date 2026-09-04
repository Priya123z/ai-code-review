# A deep read of ai-code-review

The README says what this does and how to run it. This is the long version: how
the pieces fit, why each one is the shape it is, what the tests cover, and the
questions that come up when people review it.

The short version of the argument, if you only read one paragraph: **a quality
gate that cannot tell "your code is fine" from "I could not read your code" is
worse than no gate at all.** Most of the design here is downstream of taking that
seriously.

- [1. What it is](#1-what-it-is)
- [2. Every file, and why it exists](#2-every-file-and-why-it-exists)
- [3. One scan, end to end](#3-one-scan-end-to-end)
- [4. The three capabilities](#4-the-three-capabilities)
- [5. The schema, and the field that matters most](#5-the-schema-and-the-field-that-matters-most)
- [6. The provider chain](#6-the-provider-chain)
- [7. Cross-file context](#7-cross-file-context)
- [8. The quality gate](#8-the-quality-gate)
- [9. Three delivery surfaces](#9-three-delivery-surfaces)
- [10. The HTTP service, and why the demo does not use it](#10-the-http-service-and-why-the-demo-does-not-use-it)
- [11. Configuration](#11-configuration)
- [12. Testing a thing that calls a model](#12-testing-a-thing-that-calls-a-model)
- [13. CI](#13-ci)
- [14. Running it yourself](#14-running-it-yourself)
- [15. Bugs worth knowing about](#15-bugs-worth-knowing-about)
- [16. What it does not do](#16-what-it-does-not-do)
- [17. FAQ](#17-faq)

---

## 1. What it is

### If you do not write software

When a programmer changes something, another programmer reads the change before
it ships. That review catches things no machine can: is this the right feature,
does it fit the product, is this a sensible way to do it.

But a lot of what a reviewer actually spends attention on is not that. It is
*"this will crash when the list is empty"* and *"nothing tests this path"*.
Mechanical, boring, and easy to miss on a Friday afternoon.

This tool reads changed files with a language model and writes those boring
findings down first, so that by the time a person opens the review, the
mechanical half is already done and their attention is free for the half that
needs judgement.

The important part is what it does when it *cannot* do that. If the model is
unreachable, it says so and fails, rather than reporting zero problems. Zero
problems and "I could not look" produce identical-looking output, and only one of
them means your code is fine.

### If you write software

A Python package with three capabilities, three delivery surfaces, and a strict
boundary between the model and everything else.

```bash
ai-review scan . --diff --fail-on-gate     # review what changed, gate the build
ai-review gen-tests ./src                  # emit .feature and .py files
ai-review heal --selector '#pay' --html page.html
```

Everything an LLM returns is parsed into a Pydantic model before anything else
touches it. The report is a `Report` object; the HTML and the JSON are both
rendered from it; the gate reads properties off it. Nothing downstream handles a
raw dict.

### If you are reviewing the design

Three things are worth your time.

**`FileReport.error`** ([section 5](#5-the-schema-and-the-field-that-matters-most)).
One string field, and the reason the gate can be trusted. Without it, a provider
outage produced a report with zero findings and a passing gate, which is exactly
what clean code produces.

**The provider chain** ([section 6](#6-the-provider-chain)). Two providers tried
in order, reporting which one actually answered. Built because two OpenRouter
free models returned 429 on the very first call during development.

**The test suite** ([section 12](#12-testing-a-thing-that-calls-a-model)). 45
tests, no API key, no network. The model is behind an interface with one method,
so the whole pipeline is testable against a fake that returns whatever a test
needs, including malformed output.

---

## 2. Every file, and why it exists

```
ai_review/
├── cli.py                    argparse, the three subcommands, exit codes
├── core/
│   ├── config.py             every setting, all env-overridable
│   ├── collector.py          which files get reviewed, and in diff mode which changed
│   └── pipeline.py           collect, analyze, assemble, render
├── providers/
│   ├── base.py               the interface, and extract_json
│   ├── groq.py               primary
│   ├── openrouter.py         fallback
│   └── chain.py              try each in order, report who answered
├── analyzers/
│   ├── defects.py            the review prompt, and its parsing
│   ├── specs.py              requirement to Gherkin and pytest
│   ├── selfheal.py           broken locator to a working one
│   └── context.py            the cross-file signature index
├── report/
│   ├── schema.py             Pydantic models, risk score, gate inputs
│   ├── render.py             Report to HTML and JSON
│   └── emit.py               Report to real .feature and .py files on disk
└── templates/report.html.j2

server/                       FastAPI over the same three capabilities
tests/                        45 tests, no key, no network
examples/flask_shop/          three files with deliberate bugs, for demos
sample-report/                a committed real run, published to Pages
action.yml                    the composite GitHub Action
```

The layering rule is the same one I use in test frameworks: **each layer may
call the one below it and not the other way round.** `analyzers/` knows about
`providers/` and `report/`; `providers/` knows about nothing in this package
except `providers/base.py`. The practical payoff is that `providers/` is the only
directory that does HTTP, so "what does this talk to" has a one-directory answer.

---

## 3. One scan, end to end

```
ai-review scan ./src --diff --fail-on-gate
        |
   Config           env vars, then flags on top
        |
   collect(cfg)     walk, or `git diff --name-only` in diff mode
        |            filter by extension, exclude tests, cap at max_files
        |
   for each file:
        |
     build_repo_context(sources, skip_path=this_file)
        |            signatures of the OTHER files in the change set
        |
     analyze_file(client, src, repo_context)
        |            prompt -> provider chain -> JSON -> FileReport
        |            on exception: FileReport(error=str(exc)), keep going
        |
   Report(files=[...])
        |
   write_report()   report.json and report.html
        |
   gate             risk_score, criticals, highs, and reviewed_count
        |
   exit 0 or 2
```

The loop in `pipeline.run` catches per file rather than aborting:

```python
except Exception as exc:  # keep going; note the failure in the report
    file_reports.append(
        FileReport(path=src.path, language=src.language,
                   summary=f"Not reviewed: {exc}", error=str(exc))
    )
```

Eleven files reviewed and one failed is a useful result, so a single failure does
not throw the other eleven away. But the failure is *recorded*, and
[section 8](#8-the-quality-gate) is about why that matters more than it looks.

---

## 4. The three capabilities

### Defects (`analyzers/defects.py`)

The main one. A file plus the signatures of its neighbours goes in, and a
`FileReport` comes out: findings with a severity, a category, a line number, why
it breaks and how to fix it, plus the tests that would have caught each one.

The prompt is a module constant with a version string, so changing review
strategy touches one file. One clause is worth quoting:

> You NEVER invent issues to look thorough. If the code is clean, you say so with
> an empty findings list.

Without something like it, a model asked to find problems will find problems,
because that is what it was asked to do. A reviewer that always finds three
things is one nobody reads after a fortnight.

The parse loop is deliberately forgiving in one specific way:

```python
except Exception:
    continue  # a single malformed finding never sinks the whole file
```

If one finding out of eight is malformed, seven good findings still reach the
report. This is a different judgement from the file-level one, and the reasoning
is that a dropped finding degrades the result while a dropped file changes what
the gate means.

### Specs (`analyzers/specs.py`)

A requirement in, Gherkin scenarios and pytest skeletons out. `emit.py` writes
them to disk as real files: a `.feature` per source file and a pytest module.

Real files rather than a screenshot, because the value is in committing them and
filling them in.

### Self-heal (`analyzers/selfheal.py`)

A selector that stopped matching, plus the current markup, in; a working
Playwright locator out. It prefers `get_by_role`, then `get_by_label`, then
`get_by_test_id`, then text, then CSS, which is Playwright's own recommended
order and produces locators that survive the next redesign.

The docstring is careful about scope, and rightly:

> an honest, verifiable step, and the engineer still reviews the suggestion.

It suggests a locator. It does not edit your test file.

---

## 5. The schema, and the field that matters most

```python
class FileReport(BaseModel):
    ...
    # Set when the file could not be reviewed at all. Without this a provider
    # outage looked identical to a clean file: no findings, gate passes.
    error: str = ""
```

This is the most important line in the repository and it is a two-word default.

The bug it fixes is worth spelling out, because the class of bug is common and
the specific instance is nasty.

**Before.** Provider goes down mid-run. Every file raises. The pipeline catches
per file and appends a `FileReport` with no findings. The `Report` therefore has
zero findings, a risk score of zero, zero criticals, zero highs. The gate passes.
CI goes green. A pull request merges with a badge saying it was reviewed.

Nothing anywhere was wrong, exactly. Every component did what it was told. The
composition of them produced a confident green result about code nobody looked at.

**After.** The failure is on the record, and the `Report` exposes it as data:

```python
@property
def failed_files(self) -> List[FileReport]:
    return [fr for fr in self.files if fr.error]

@computed_field
@property
def reviewed_count(self) -> int:
    return len(self.files) - len(self.failed_files)
```

Now the gate can ask *how many files were actually reviewed*, and the CLI can
say:

```
✕ no files could be reviewed, so not reporting a result.
```

and exit 2. Which it does, verifiably:

```bash
$ GROQ_API_KEY=nonsense ai-review scan examples/flask_shop --fail-on-gate
...
! 3 of 3 file(s) could not be reviewed:
    payments.py: every provider failed. groq: Groq returned 401: Invalid API Key
    ...
✕ no files could be reviewed, so not reporting a result.
$ echo $?
2
```

The general lesson: **an absence of findings is not evidence of absence of
problems, and any system that reports one as the other will eventually be
believed.** If you build a gate, make it able to distinguish "checked, found
nothing" from "did not check".

### The rest of the schema

`Severity` is an enum with a `weight`, and `risk_score` sums the weights:

```python
@computed_field
@property
def risk_score(self) -> int:
    return sum(f.severity.weight for f in self.all_findings)
```

One number a pipeline can threshold on. Weighted rather than counted, because
twelve low-severity style notes should not outrank one critical.

`@computed_field` matters: it means these derive on the object *and* appear in
`model_dump()`, so `report.json` carries the same numbers the gate used. A
consumer reading the JSON cannot disagree with the gate about the score.

---

## 6. The provider chain

```python
def _through(self, call):
    errors = []
    for client in self.clients:
        try:
            result = call(client)
            self.served_by = client.name
            self._served = client
            return result
        except (QuotaExhausted, LLMError) as exc:
            errors.append(f"{client.name}: {exc}")
    raise QuotaExhausted("every provider failed. " + "; ".join(errors))
```

Groq first: 1,000 requests a day against OpenRouter's 50, a real JSON mode, and
sub-second answers. OpenRouter behind it.

Three details are load-bearing.

**`served_by` is reported.** The CLI prints which provider actually answered, and
so does the API. A fallback that happens silently is a fallback you find out
about from a bill or a quality drop.

```python
@property
def model(self) -> str:
    # The provider that answered, not the one we tried first.
    client = self._served or (self.clients[0] if self.clients else None)
    return client.model if client else ""
```

**The error names every provider.** Not "it failed" but "groq: 401 Invalid API
Key; openrouter: rate limited". When both fail, you need to know whether that is
one cause or two.

**A model slug belongs to one provider.** This was a real bug:

```python
if model:
    if "/" in model and model.endswith(":free"):
        openrouter.model = model
    else:
        groq.model = model
```

Passing `--model nvidia/nemotron:free` used to set that slug on *both* clients.
Groq did not recognise it, quietly fell back to another model, and answered.
So you got results from a model you did not ask for, with nothing saying so.
Now the slug goes only to the provider it belongs to.

Inside `GroqClient` there is a second, smaller chain: `FALLBACK_MODELS` is tried
when the preferred model is busy, and a `QuotaExhausted` breaks to the next model
rather than sleeping out the request budget on a busy one.

---

## 7. Cross-file context

```python
repo_context = build_repo_context(sources, skip_path=src.path)
```

Before each file is reviewed, `context.py` builds an index of the class and
function signatures of the *other* files in the change set, and that goes into
the prompt.

This is the difference between per-file review and something more useful. Given
`payments.py` alone, a model can tell you a function is missing a null check.
Given `payments.py` plus the knowledge that `auth.py` exposes `issue_token()` and
`verify_token()`, it can tell you that payments never verifies the token auth
issues, which is the kind of finding worth having.

Signatures only, not bodies. Bodies would blow the context window on any real
repository and would mostly be noise; what a reviewer needs from a neighbouring
file is its surface.

`skip_path` keeps the file under review out of its own context, so the model is
not handed the same code twice in two formats.

---

## 8. The quality gate

Two thresholds, both env-overridable:

```
AI_REVIEW_MAX_CRITICAL   default 0
AI_REVIEW_MAX_HIGH       default 3
```

`--fail-on-gate` turns the verdict into an exit code. Without it, the CLI prints
the verdict and exits 0:

```
(not failing the build; pass --fail-on-gate to enforce)
```

That default is deliberate. A gate that starts enforcing on the day you install
it produces one red build, one annoyed team, and one deleted workflow file. The
README says to run it advisory for a week first and look at what it flags.

But the gate's real precondition is the one from
[section 5](#5-the-schema-and-the-field-that-matters-most): if nothing was
reviewed, there is no verdict to give, and the CLI refuses to give one. A gate
whose failure mode is "pass" is not a gate.

---

## 9. Three delivery surfaces

**CLI.** `ai-review scan | gen-tests | heal`. Exit codes: 0 fine, 1 gate failed,
2 could not run.

One detail at the top of `main()` is worth mentioning, because it looks like
nothing:

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
```

Python block-buffers stdout when it is redirected, which a CI log always is. So a
thirty-second scan printed nothing at all and then dumped every progress line at
once when the process exited. Worse, stderr is *not* buffered, so the warnings
appeared above the summary they were about. A job that prints nothing for half a
minute looks hung, and output in the wrong order is read in the wrong order.

One line, invisible on a terminal, and it only shows up the first time you watch
the thing run in CI.

**GitHub Action.** `action.yml`, a composite action that installs the package and
runs it. `.github/workflows/code-review.yml` uses it and posts findings as a pull
request comment.

**HTTP.** `server/`, covered next.

All three call `pipeline.run` or an analyzer directly. There is no logic in any
surface that is not also in the others.

---

## 10. The HTTP service, and why the demo does not use it

`server/` is a FastAPI app over the same three capabilities, for a team that
wants one shared instance rather than everyone installing a CLI and finding a
key. It has request budgeting (`quota.py`), a response cache (`cache.py`), and
the same degrade-to-a-saved-answer behaviour the browser demos have.

It is not deployed. Hugging Face made Docker Spaces a paid feature partway
through building it. The Dockerfile runs anywhere and `deploy-space.sh` will push
it to a Space if you have PRO.

The browser demos on the portfolio are served by something much smaller: a
Cloudflare Worker on the free plan holding a Groq key as a secret, which
reimplements the three prompts in JavaScript. It lives
[in the portfolio repository](https://github.com/Priya123z/Priya123z.github.io/tree/main/worker).

Which is worth being clear about, because "why two backends" is a fair question.
They are not the same product:

| | `server/` | the Worker |
|---|---|---|
| Runs | the real pipeline | three prompts |
| Cross-file context | yes | no |
| The gate, emitted test files | yes | no |
| Needs | a container host | a free Cloudflare account |
| For | a team, behind an HTTP boundary | a static page, for nothing |

`quota.py` is worth reading even though it is not deployed, because it counts the
right thing:

```python
TOKENS_PER_MINUTE = 7000
```

Groq's free tier allows 30 requests a minute and 8,000 tokens a minute. A couple
of two-thousand-token reviews exhaust the token allowance long before they get
near thirty requests, so budgeting by request count would have let the demo sail
past the limit and collect 429s. It counts tokens, and refuses before sending
rather than after a 429 comes back.

---

## 11. Configuration

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | none | Primary provider |
| `OPENROUTER_API_KEY` | none | Fallback |
| `AI_REVIEW_MODEL` | provider default | Overridden by `--model` |
| `AI_REVIEW_MAX_FILES` | `12` | Cap per run |
| `AI_REVIEW_MAX_CRITICAL` | `0` | Gate threshold |
| `AI_REVIEW_MAX_HIGH` | `3` | Gate threshold |
| `AI_REVIEW_DIFF_BASE` | `origin/main` | What `--diff` compares against |
| `ALLOWED_ORIGINS` | the portfolio origin | CORS, `server/` only |

`config.py` contains a fix worth copying into your own dataclasses:

```python
def _env(name, default=""):
    return field(default_factory=lambda: os.getenv(name, default))
```

A dataclass default expression is evaluated once, when the module is imported.
Writing `model: str = os.getenv("AI_REVIEW_MODEL", "")` means the variable is
read at import time, so exporting it afterwards has no effect. `default_factory`
defers it to instantiation. This is a classic and it is silent: nothing errors,
the setting just does not apply.

The empty default for `model` is also deliberate: it means "let the provider
pick", so a Groq key gets a Groq model and an OpenRouter key gets an OpenRouter
one. See the bug in [section 6](#6-the-provider-chain).

---

## 12. Testing a thing that calls a model

45 tests. No API key, no network, and they finish in under half a second.

That is possible because the model sits behind an interface with essentially one
method:

```python
class BaseClient:
    def chat(self, system, user, as_json=False) -> str: ...
    def chat_json(self, system, user) -> dict:
        return extract_json(self.chat(system, user, as_json=True))
```

`tests/conftest.py` provides a fake that returns whatever the test needs. Which
means the tests can cover things a live model could never be relied on to
produce:

- **Malformed JSON** in the response, and the finding count that survives it
- **A finding with a bad severity**, and that the other findings still land
- **Every provider failing**, and that `FileReport.error` gets set
- **A file that errors**, and that `reviewed_count` and the gate reflect it
- **Fenced JSON**, and that `extract_json` unwraps it

The split is the same one I would defend anywhere: **test your handling of the
model's output, not the model.** Whether the model finds a given bug is not a
property of this code and is not deterministic. Whether this code does the right
thing when handed a malformed response absolutely is.

`tests/test_server.py` covers the FastAPI app the same way, including the
degrade-to-cached path, so the untested-because-undeployed service is not
actually untested.

There are no tests asserting on model output text anywhere, on purpose.

---

## 13. CI

**`tests.yml`** runs the 45 tests with no key, because they need none.

It also does something less obvious. There is a second job that actually executes
`action.yml`:

```yaml
# action.yml would have shipped green. The README tells people to use it, and
# nothing had ever run it.
```

The unit tests import the package. They do not install it the way a consumer
does, run the composite action's steps, or exercise the console script entry
point. The action could have been broken for a release and every badge would have
stayed green. The job skips with a warning when no provider secret is present, so
forks still pass.

**`code-review.yml`** runs the tool on its own pull requests and comments the
findings. It skips the live scan with a warning when no secret is set rather than
failing, for the same reason.

The general point: **a badge only covers what CI actually runs.** Anything a
README tells people to do that CI does not do is untested, however green
everything looks.

---

## 14. Running it yourself

```bash
git clone https://github.com/Priya123z/ai-code-review.git
cd ai-code-review
python -m venv .venv && source .venv/bin/activate
pip install -e .

pytest -q                                  # 45 passed, no key needed
```

With a key (free at [console.groq.com/keys](https://console.groq.com/keys)):

```bash
export GROQ_API_KEY=gsk_...
ai-review scan examples/flask_shop
open report/report.html
```

`examples/flask_shop/` has three files with deliberate bugs: a mutable default
argument, an unguarded division, a token that is issued but never verified across
a file boundary. The last one is the one that needs cross-file context, so it is
the interesting one to check.

Proving the outage behaviour to yourself takes one command:

```bash
GROQ_API_KEY=definitely_not_a_key ai-review scan examples/flask_shop --fail-on-gate
echo $?     # 2, with an explanation, not 0 with zero findings
```

---

## 15. Bugs worth knowing about

Every one of these shipped, and each left a mark on the code.

**A provider outage passed the gate.** The headline one.
[Section 5](#5-the-schema-and-the-field-that-matters-most).

**A model slug went to both providers.** `--model` set an OpenRouter slug on the
Groq client too. Groq did not recognise it, silently fell back, and answered, so
you got results from a model you had not asked for. Fixed in `build_client`.

**Env vars were read at import time.** Dataclass defaults evaluate once. Setting
`AI_REVIEW_MAX_FILES` after the first import did nothing, silently.
[Section 11](#11-configuration).

**CI showed no progress and printed the verdict in the wrong order.** stdout
block-buffers when it is not a terminal, so the run looked hung and then dumped
everything at once, out of order relative to unbuffered stderr.
[Section 9](#9-three-delivery-surfaces).

**Nothing had ever executed the Action.** [Section 13](#13-ci).

**The published landing page shipped a copy-paste snippet that did not work.** It
named the pre-rename repository, pinned a tag whose package no longer existed,
and referenced the fallback provider's key rather than the primary one. Anyone
following the README's own instructions got a failing workflow.

The pattern across all six: none of them threw an exception. Every one produced
plausible output that was wrong. That is the failure mode worth designing
against, and it is why so much of this codebase is about making the difference
between "worked" and "did not work" impossible to miss.

---

## 16. What it does not do

**It is not the review.** It has no idea what your product is supposed to do, so
it cannot tell you a feature is wrong. It can tell you a line is likely to behave
badly. Treat it as the pass before the one that matters.

**Python only, by default.** `DEFAULT_INCLUDE = [".py"]`. The analyzers are not
Python-specific and adding an extension is a config change, but nothing else has
been exercised.

**No incremental state.** Every run is from scratch. It cannot tell you "this
finding is new since last week", which is what you would actually want from a
gate. Storing previous reports and diffing them is the obvious next thing.

**Findings are not deduplicated across files.** The same class of issue in six
files is six findings.

**`max_files` defaults to 12.** A large repository gets a sample, not a review.
That is a free-tier constraint honestly represented rather than a design goal.

**Confidence scores are the model's own.** They are reported, not calibrated, and
should be read as a hint rather than a probability.

---

## 17. FAQ

**Why not just use a linter?**
Use both. A linter tells you `total / len(items)` is valid Python. It cannot tell
you `items` is empty whenever a cart is new, that nothing tests that path, and
that the fix belongs in `__init__` rather than at the call site.

**How do you know it is not making things up?**
Partly you do not, and that is why it is advisory by default and why every
finding carries a line number and an explanation you can check in seconds. What
the design *can* guarantee is the structural half: output that does not fit the
schema never reaches a report, and a run that did not happen never reports a
pass.

**Why two providers?**
Free tiers rate limit without warning. Two OpenRouter free models returned 429 on
the very first call during development. One provider is not enough to keep
anything public working.

**Why Pydantic and not a dict?**
So that everything downstream can stop defending itself. `render.py` does not
check whether `findings` exists; it cannot not exist. Validation happens once, at
the boundary, and the type carries the guarantee from there.

**Why does a malformed finding get skipped but a malformed file get recorded?**
Different blast radius. A dropped finding makes the result slightly less
complete. A dropped file changes what the gate means, so it has to be visible.

**Can I run it without a key?**
The tests, yes: 45 of them, no key, no network. The tool itself needs a provider,
and refuses with exit 2 rather than pretending.

**Why is `--fail-on-gate` opt-in?**
Because a gate that starts enforcing on install produces one red build and one
deleted workflow file. Run it advisory for a week and look at what it flags
first.

**Is `server/` dead code?**
It is undeployed, not untested. `tests/test_server.py` covers it, including the
degrade-to-cached path, and the Dockerfile runs anywhere. It answers a different
question from the Worker: see [section 10](#10-the-http-service-and-why-the-demo-does-not-use-it).

**What is the single most important line?**
`error: str = ""` on `FileReport`. Everything else is engineering; that one is the
difference between a gate you can trust and a gate that goes green when nobody
looked.
