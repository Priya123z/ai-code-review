"""Runtime configuration — everything env-overridable so CI stays declarative."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

DEFAULT_INCLUDE = [".py"]
DEFAULT_EXCLUDE = [
    "/.git/", "/.venv/", "/venv/", "/node_modules/", "/__pycache__/",
    "/site-packages/", "/dist/", "/build/", "/tests/", "test_",
]


@dataclass
class Config:
    target: str = "."
    out_dir: str = "report"
    model: str = os.getenv("AIQA_MODEL", "deepseek/deepseek-chat-v3.1")
    include_ext: List[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE))
    exclude_globs: List[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    max_files: int = int(os.getenv("AIQA_MAX_FILES", "12"))
    max_bytes_per_file: int = 16_000
    diff_only: bool = False
    diff_base: str = os.getenv("AIQA_DIFF_BASE", "origin/main")
    # CI gate thresholds
    max_critical: int = int(os.getenv("AIQA_MAX_CRITICAL", "0"))
    max_high: int = int(os.getenv("AIQA_MAX_HIGH", "3"))
    project_name: str = os.getenv("AIQA_PROJECT", "")
