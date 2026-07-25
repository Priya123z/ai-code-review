"""Command line entry point.

    aiqa scan ./src --out report/
    aiqa scan . --diff --fail-on-gate
"""
from __future__ import annotations

import argparse
import sys

from .core.config import Config
from .core.pipeline import run_and_write
from .providers.openrouter import LLMClient


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aiqa", description="AI QA Copilot — scan code, find defects, generate tests, render a report.")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Analyze a path and write an HTML/JSON report.")
    scan.add_argument("target", nargs="?", default=".", help="File or directory to analyze (default: .)")
    scan.add_argument("--out", default="report", help="Output directory (default: report/)")
    scan.add_argument("--model", default=None, help="OpenRouter model slug (or set AIQA_MODEL)")
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
    client = LLMClient(model=cfg.model)
    if not client.configured:
        print("error: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        print("  export OPENROUTER_API_KEY=sk-or-...   (or add it as a GitHub Actions secret)", file=sys.stderr)
        return 2

    print(f"aiqa · model={client.model} · target={cfg.target}")
    report, paths = run_and_write(cfg, client=client, progress=lambda m: print("  " + m))

    b = report.severity_breakdown
    print("\n── summary ─────────────────────────────")
    print(f"  risk score : {report.risk_score}")
    print(f"  findings   : {len(report.all_findings)}  "
          f"(critical {b['critical']}, high {b['high']}, medium {b['medium']}, low {b['low']})")
    print(f"  tests      : {len(report.all_tests)} suggested")
    print(f"  report     : {paths['html']}")
    print(f"  json       : {paths['json']}")

    if args.emit_tests:
        from .report.emit import emit_tests
        counts = emit_tests(report, args.emit_tests)
        print(f"  tests      : wrote {counts['features']} .feature + "
              f"{counts['pytest_modules']} pytest file(s) to {args.emit_tests}/")

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


def _require_key(client: LLMClient) -> bool:
    if not client.configured:
        print("error: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        return False
    return True


def _cmd_gen_tests(args) -> int:
    from .core.config import Config
    from .core.pipeline import run
    from .report.emit import emit_tests

    client = LLMClient(model=args.model or Config().model)
    if not _require_key(client):
        return 2
    cfg = Config(target=args.target)
    if args.max_files is not None:
        cfg.max_files = args.max_files
    print(f"aiqa gen-tests · model={client.model} · target={cfg.target}")
    report = run(cfg, client=client, progress=lambda m: print("  " + m))
    counts = emit_tests(report, args.out)
    print(f"\n✓ wrote {counts['features']} .feature + {counts['pytest_modules']} "
          f"pytest file(s) to {args.out}/")
    return 0


def _cmd_heal(args) -> int:
    import json as _json

    from .analyzers.selfheal import heal_locator
    from .core.config import Config

    client = LLMClient(model=args.model or Config().model)
    if not _require_key(client):
        return 2
    try:
        html = open(args.html, encoding="utf-8").read()
    except OSError as exc:
        print(f"error: cannot read HTML: {exc}", file=sys.stderr)
        return 2
    print(f"aiqa heal · model={client.model}")
    result = heal_locator(client, args.selector, html, args.desc)
    print(_json.dumps(result.model_dump(), indent=2))
    return 0 if result.found else 1


if __name__ == "__main__":
    raise SystemExit(main())
