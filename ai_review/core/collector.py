"""Decide *what* to send to the model: whole tree, or only the changed files."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List

from .config import Config


@dataclass
class SourceFile:
    path: str          # path as displayed (relative to target)
    abspath: str
    content: str
    language: str = "python"


def _language_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lstrip(".")
    return {"py": "python", "js": "javascript", "ts": "typescript", "java": "java"}.get(ext, ext or "text")


def _excluded(rel: str, cfg: Config) -> bool:
    norm = "/" + rel.replace(os.sep, "/")
    return any(pat in norm for pat in cfg.exclude_globs)


def _changed_files(cfg: Config) -> List[str]:
    """Files changed against the diff base, which is what PR mode reviews."""
    try:
        out = subprocess.run(
            ["git", "-C", cfg.target, "diff", "--name-only", f"{cfg.diff_base}...HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        names = [n for n in out.stdout.splitlines() if n.strip()]
        if not names:  # fall back to unstaged/staged working changes
            out = subprocess.run(
                ["git", "-C", cfg.target, "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
            names = [n for n in out.stdout.splitlines() if n.strip()]
        return names
    except Exception:
        return []


def collect(cfg: Config) -> List[SourceFile]:
    files: List[SourceFile] = []

    if cfg.diff_only:
        candidates = [os.path.join(cfg.target, n) for n in _changed_files(cfg)]
    elif os.path.isfile(cfg.target):
        candidates = [cfg.target]
    else:
        candidates = []
        for root, _dirs, names in os.walk(cfg.target):
            for name in names:
                candidates.append(os.path.join(root, name))

    for abspath in candidates:
        if not os.path.isfile(abspath):
            continue
        ext = os.path.splitext(abspath)[1]
        if cfg.include_ext and ext not in cfg.include_ext:
            continue
        rel = os.path.relpath(abspath, cfg.target if os.path.isdir(cfg.target) else os.path.dirname(cfg.target))
        if _excluded(rel, cfg):
            continue
        try:
            with open(abspath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read(cfg.max_bytes_per_file)
        except OSError:
            continue
        if not content.strip():
            continue
        files.append(SourceFile(path=rel, abspath=abspath, content=content, language=_language_for(abspath)))
        if len(files) >= cfg.max_files:
            break
    return files
