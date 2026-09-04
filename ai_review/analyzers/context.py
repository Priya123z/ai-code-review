"""Lightweight retrieval-augmented context.

Before reviewing a file, we give the model a compact map of the *other* modules
in the change set: their classes and function signatures. That cross-file
context is what lets the review catch integration defects a single-file linter
never could (e.g. "payments.process_order never verifies the token that
auth.current_user issues"). It's RAG in miniature: retrieve related code, then
augment the generation prompt with it  no vector DB required for a change set
this size.
"""
from __future__ import annotations

import re
from typing import List

from ..core.collector import SourceFile

_SIG = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+[^\n]+", re.MULTILINE)


def build_repo_context(sources: List[SourceFile], skip_path: str = "", max_per_file: int = 12) -> str:
    """A one-line-per-signature summary of sibling modules, excluding skip_path."""
    blocks = []
    for src in sources:
        if src.path == skip_path:
            continue
        sigs = [s.strip().rstrip(":") for s in _SIG.findall(src.content)][:max_per_file]
        if sigs:
            blocks.append(f"# {src.path}\n" + "\n".join(sigs))
    return "\n\n".join(blocks)
