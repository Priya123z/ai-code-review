"""Lightweight retrieval-augmented context.

Before reviewing a file, the model gets a compact map of the *other* modules in
the change set: their classes and function signatures. That cross-file context
is what lets the review catch an integration defect a single-file linter never
could, of the shape "payments.process_order never verifies the token that
auth.current_user issues".

Retrieve the related code, then put it in the prompt. No vector database, for a
change set this size.
"""
import re

_SIG = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+[^\n]+", re.MULTILINE)


def build_repo_context(sources, skip_path="", max_per_file=12):
    """A one-line-per-signature summary of sibling modules, excluding skip_path."""
    blocks = []
    for src in sources:
        if src.path == skip_path:
            continue
        sigs = [s.strip().rstrip(":") for s in _SIG.findall(src.content)][:max_per_file]
        if sigs:
            blocks.append(f"# {src.path}\n" + "\n".join(sigs))
    return "\n\n".join(blocks)
