"""Runtime configuration. Everything is env-overridable so CI stays declarative."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

DEFAULT_INCLUDE = [".py"]
DEFAULT_EXCLUDE = [
    "/.git/", "/.venv/", "/venv/", "/node_modules/", "/__pycache__/",
    "/site-packages/", "/dist/", "/build/", "/tests/", "test_",
]


# These read the environment through default_factory rather than in the default
# expression, which is evaluated once when the module is imported. Exporting a
# variable after the first import used to have no effect.
def _env(name, default=""):
    return field(default_factory=lambda: os.getenv(name, default))


def _env_int(name, default):
    return field(default_factory=lambda: int(os.getenv(name, default)))


@dataclass
class Config:
    target: str = "."
    out_dir: str = "report"
    # Empty means "let the provider pick", so a Groq key gets a Groq model and an
    # OpenRouter key gets an OpenRouter one. Naming a specific slug here used to send
    # an OpenRouter slug to Groq, which then quietly fell back to another model.
    model: str = _env("AI_REVIEW_MODEL")
    include_ext: List[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE))
    exclude_globs: List[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    max_files: int = _env_int("AI_REVIEW_MAX_FILES", "12")
    max_bytes_per_file: int = 16_000
    diff_only: bool = False
    diff_base: str = _env("AI_REVIEW_DIFF_BASE", "origin/main")
    # CI gate thresholds
    max_critical: int = _env_int("AI_REVIEW_MAX_CRITICAL", "0")
    max_high: int = _env_int("AI_REVIEW_MAX_HIGH", "3")
    project_name: str = _env("AI_REVIEW_PROJECT")
