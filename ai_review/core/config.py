"""Runtime configuration. Everything is env-overridable so CI stays declarative."""
import os

DEFAULT_INCLUDE = [".py"]
DEFAULT_EXCLUDE = [
    "/.git/", "/.venv/", "/venv/", "/node_modules/", "/__pycache__/",
    "/site-packages/", "/dist/", "/build/", "/tests/", "test_",
]


class Config:
    # The environment is read here, per instance, not in default arguments,
    # which are evaluated once at import. Exporting a variable after the first
    # import used to have no effect.
    def __init__(self, target=".", out_dir="report", diff_only=False, max_files=None):
        self.target = target
        self.out_dir = out_dir
        self.diff_only = diff_only
        # Empty means "let the provider pick", so a Groq key gets a Groq model
        # and an OpenRouter key gets an OpenRouter one. Naming a slug here used
        # to send an OpenRouter slug to Groq, which quietly fell back to another
        # model.
        self.model = os.getenv("AI_REVIEW_MODEL", "")
        self.include_ext = list(DEFAULT_INCLUDE)
        self.exclude_globs = list(DEFAULT_EXCLUDE)
        self.max_files = max_files or int(os.getenv("AI_REVIEW_MAX_FILES", "12"))
        self.max_bytes_per_file = 16_000
        self.diff_base = os.getenv("AI_REVIEW_DIFF_BASE", "origin/main")
        self.project_name = os.getenv("AI_REVIEW_PROJECT", "")
        # CI gate thresholds
        self.max_critical = int(os.getenv("AI_REVIEW_MAX_CRITICAL", "0"))
        self.max_high = int(os.getenv("AI_REVIEW_MAX_HIGH", "3"))
