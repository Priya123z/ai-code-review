"""Orchestrator: collect → analyze (per file) → assemble → render.

Kept deliberately small; the interesting logic lives in the analyzers and the
schema. This is the seam the CLI and the GitHub Action both call.
"""
import os
import subprocess

from ..analyzers.context import build_repo_context
from ..analyzers.defects import PROMPT_VERSION, analyze_file
from ..providers.chain import build_client
from ..report import schema
from ..report.render import write_report
from .collector import collect


def _git_commit(target):
    try:
        out = subprocess.run(
            ["git", "-C", target, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def run(cfg, client=None, progress=None):
    say = progress or (lambda _m: None)
    client = client or build_client(model=cfg.model)

    target_dir = cfg.target if os.path.isdir(cfg.target) else os.path.dirname(cfg.target) or "."
    project = cfg.project_name or os.path.basename(os.path.abspath(target_dir))

    sources = collect(cfg)
    say(f"Collected {len(sources)} file(s) to review.")

    file_reports = []
    for i, src in enumerate(sources, 1):
        say(f"[{i}/{len(sources)}] Reviewing {src.path} …")
        try:
            repo_context = build_repo_context(sources, skip_path=src.path)
            file_reports.append(analyze_file(client, src, repo_context=repo_context))
        except Exception as exc:  # keep going; note the failure in the report
            say(f"    could not review {src.path}: {exc}")
            file_reports.append(schema.file_report(
                path=src.path,
                language=src.language,
                summary=f"Not reviewed: {exc}",
                error=str(exc),
            ))

    report = schema.report(
        project=project,
        model=client.model,
        commit=_git_commit(target_dir),
        files=file_reports,
        notes=f"Prompt {PROMPT_VERSION}. {len(sources)} file(s) analyzed.",
    )
    b = report["severity_breakdown"]
    say(f"Done. risk_score={report['risk_score']} critical={b['critical']} high={b['high']}")
    return report


def run_and_write(cfg, client=None, progress=None, max_critical=0, max_high=3):
    report = run(cfg, client=client, progress=progress)
    # The thresholds reach the renderer so the gate banner in the HTML says the
    # same thing the exit code does. It used to render the defaults regardless.
    paths = write_report(report, cfg.out_dir, max_critical, max_high)
    return report, paths
