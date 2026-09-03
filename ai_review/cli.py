"""Command line entry point.

    ai-review scan ./src --out report/
    ai-review scan . --diff --fail-on-gate
"""
from __future__ import annotations

import argparse
import sys

from .core.config import Config
from .core.pipeline import run_and_write
from .providers.chain import build_client
from .providers.base import BaseClient


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai-review", description="Scan code with an LLM: find defects, suggest tests, render a report.")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Analyze a path and write an HTML/JSON report.")
    scan.add_argument("target", nargs="?", default=".", help="File or directory to analyze (default: .)")
    scan.add_argument("--out", default="report", help="Output directory (default: report/)")
    scan.add_argument("--model", default=None, help="OpenRouter model slug (or set AI_REVIEW_MODEL)")
    scan.add_argument("--diff", action="store_true", help="Only analyze files changed vs the diff base")
    scan.add_argument("--diff-base", default=None, help="Git ref to diff against (default: origin/main)")
    scan.add_argument("--max-files", type=int, default=None, help="Cap number of files analyzed")
    scan.add_argument("--project", default=None, help="Project name shown in the report")
    scan.add_argument("--fail-on-gate", action="store_true", help="Exit non-zero if the quality gate fails")
    scan.add_argument("--max-critical", type=int, default=None, help="Max critical findings the gate tolerates")
    scan.add_argument("--max-high", type=int, default=None, help="Max high findings the gate tolerates")
    scan.add_argument("--emit-tests", metavar="DIR", default=None,
                      help="Also write the AI-suggested tests as real .feature + pytest files into DIR")

    # gen-tests: scan a path and write ONLY the generated test files
    gen = sub.add_parser("gen-tests", help="Generate real .feature + pytest files from a path.")
    gen.add_argument("target", nargs="?", default=".")
    gen.add_argument("--out", default="generated_tests")
    gen.add_argument("--model", default=None)
    gen.add_argument("--max-files", type=int, default=None)

    # heal: repair a broken UI selector against current HTML (self-healing locators)
    heal = sub.add_parser("heal", help="Repair a broken selector into a resilient Playwright locator.")
    heal.add_argument("--selector", required=True, help="The broken selector.")
    heal.add_argument("--html", required=True, help="Path to an HTML file of the current page.")
    heal.add_argument("--desc", default="", help="What the test was targeting (optional).")
    heal.add_argument("--model", default=None)

    sub.add_parser("version", help="Print version")
    return p


def _cfg_from_args(a: argparse.Namespace) -> Config:
    cfg = Config(target=a.target, out_dir=a.out, diff_only=a.diff)
    if a.model:
        cfg.model = a.model
    if a.diff_base:
        cfg.diff_base = a.diff_base
    if a.max_files is not None:
        cfg.max_files = a.max_files
    if a.project:
        cfg.project_name = a.project
    if a.max_critical is not None:
        cfg.max_critical = a.max_critical
    if a.max_high is not None:
        cfg.max_high = a.max_high
    return cfg


def main(argv=None) -> int:
    # A redirected stdout is block buffered, so in a CI log nothing appeared until the
    # process exited: the per-file progress arrived all at once at the end, and the
    # warnings below — stderr, which is not buffered — were timestamped ahead of the
    # summary they refer to. Line buffering makes the output arrive in the order it
    # was written, and makes a 30-second scan show progress while it runs.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    args = _build_parser().parse_args(argv)

    if args.command == "version":
        from . import __version__
        print(__version__)
        return 0

    if args.command == "heal":
        return _cmd_heal(args)

    if args.command == "gen-tests":
        return _cmd_gen_tests(args)

    cfg = _cfg_from_args(args)
    client = build_client(model=cfg.model)
    if not client.configured:
        print("error: no LLM provider is configured.", file=sys.stderr)
        print("  export GROQ_API_KEY=gsk_...   (or OPENROUTER_API_KEY=sk-or-...)", file=sys.stderr)
        return 2

    print(f"ai-review · target={cfg.target}")
    report, paths = run_and_write(cfg, client=client, progress=lambda m: print("  " + m))

    # Write the emitted tests before the summary rather than after it, so the
    # summary can report them and so every line the run prints to stdout is
    # contiguous. Printing them after meant a stdout line was still to come once
    # the warnings below had started, and stdout and stderr are separate pipes —
    # a CI log interleaves them by read order, not by write order.
    emitted = None
    if args.emit_tests:
        from .report.emit import emit_tests
        emitted = emit_tests(report, args.emit_tests)

    b = report.severity_breakdown
    print("\n── summary ─────────────────────────────")
    print(f"  provider   : {client.served_by} · {client.model}")
    print(f"  risk score : {report.risk_score}")
    print(f"  findings   : {len(report.all_findings)}  "
          f"(critical {b['critical']}, high {b['high']}, medium {b['medium']}, low {b['low']})")
    print(f"  tests      : {len(report.all_tests)} suggested")
    print(f"  report     : {paths['html']}")
    print(f"  json       : {paths['json']}")
    if emitted is not None:
        print(f"  emitted    : {emitted['features']} .feature + "
              f"{emitted['pytest_modules']} pytest file(s) in {args.emit_tests}/")

    if report.incomplete:
        print(f"\n! {len(report.failed_files)} of {len(report.files)} file(s) could not be "
              f"reviewed:", file=sys.stderr)
        for fr in report.failed_files[:5]:
            print(f"    {fr.path}: {fr.error}", file=sys.stderr)

    # Nothing was reviewed, so there is nothing to say about the code. Exiting 0 here
    # would let a provider outage look like a passing gate.
    if report.files and report.reviewed_count == 0:
        print("\n✕ no files could be reviewed — not reporting a result.", file=sys.stderr)
        return 2

    gate_failed = report.gate_fails(cfg.max_critical, cfg.max_high)
    if gate_failed:
        print(f"\n✕ quality gate FAILED (critical>{cfg.max_critical} or high>{cfg.max_high})",
              file=sys.stderr)
        if args.fail_on_gate:
            return 1
        print("  (not failing the build — pass --fail-on-gate to enforce)")
        return 0
    print("\n✓ quality gate passed")
    return 0


def _require_key(client: BaseClient) -> bool:
    if not client.configured:
        print("error: no LLM provider is configured.", file=sys.stderr)
        print("  export GROQ_API_KEY=gsk_...   (or OPENROUTER_API_KEY=sk-or-...)", file=sys.stderr)
        return False
    return True


def _cmd_gen_tests(args) -> int:
    from .core.config import Config
    from .core.pipeline import run
    from .report.emit import emit_tests

    client = build_client(model=args.model or Config().model)
    if not _require_key(client):
        return 2
    cfg = Config(target=args.target)
    if args.max_files is not None:
        cfg.max_files = args.max_files
    print(f"ai-review gen-tests · model={client.model} · target={cfg.target}")
    report = run(cfg, client=client, progress=lambda m: print("  " + m))
    counts = emit_tests(report, args.out)
    print(f"\n✓ wrote {counts['features']} .feature + {counts['pytest_modules']} "
          f"pytest file(s) to {args.out}/")
    return 0


def _cmd_heal(args) -> int:
    import json as _json

    from .analyzers.selfheal import heal_locator
    from .core.config import Config

    client = build_client(model=args.model or Config().model)
    if not _require_key(client):
        return 2
    try:
        html = open(args.html, encoding="utf-8").read()
    except OSError as exc:
        print(f"error: cannot read HTML: {exc}", file=sys.stderr)
        return 2
    print(f"ai-review heal · model={client.model}")
    result = heal_locator(client, args.selector, html, args.desc)
    print(_json.dumps(result.model_dump(), indent=2))
    return 0 if result.found else 1


if __name__ == "__main__":
    raise SystemExit(main())
