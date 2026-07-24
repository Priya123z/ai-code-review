"""Orchestrator: collect → analyze (per file) → assemble → render.

Kept deliberately small; the interesting logic lives in the analyzers and the
schema. This is the seam the CLI and the GitHub Action both call.
"""
from __future__ import annotations

import os
import subprocess
from typing import Callable, List, Optional

from ..analyzers.defects import PROMPT_VERSION, analyze_file
from ..providers.openrouter import LLMClient
from ..report.render import write_report
from ..report.schema import FileReport, Report
from .collector import collect
from .config import Config

ProgressFn = Callable[[str], None]


def _git_commit(target: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", target, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def run(
    cfg: Config,
    client: Optional[LLMClient] = None,
    progress: Optional[ProgressFn] = None,
) -> Report:
    say = progress or (lambda _m: None)
    client = client or LLMClient(model=cfg.model)

    target_dir = cfg.target if os.path.isdir(cfg.target) else os.path.dirname(cfg.target) or "."
    project = cfg.project_name or os.path.basename(os.path.abspath(target_dir))

    sources = collect(cfg)
    say(f"Collected {len(sources)} file(s) to review.")

    file_reports: List[FileReport] = []
    for i, src in enumerate(sources, 1):
        say(f"[{i}/{len(sources)}] Reviewing {src.path} …")
        try:
            file_reports.append(analyze_file(client, src))
        except Exception as exc:  # keep going; note the failure in the report
            file_reports.append(
                FileReport(path=src.path, language=src.language, summary=f"Skipped: {exc}")
            )

    report = Report(
        project=project,
        model=client.model,
        commit=_git_commit(target_dir),
        files=file_reports,
        notes=f"Prompt {PROMPT_VERSION}. {len(sources)} file(s) analyzed.",
    )
    b = report.severity_breakdown
    say(f"Done. risk_score={report.risk_score} critical={b['critical']} high={b['high']}")
    return report


def run_and_write(cfg: Config, client: Optional[LLMClient] = None, progress: Optional[ProgressFn] = None):
    report = run(cfg, client=client, progress=progress)
    paths = write_report(report, cfg.out_dir)
    return report, paths
