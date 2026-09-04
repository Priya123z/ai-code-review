"""Pydantic contracts for everything the pipeline produces.

The whole point of validating LLM output through Pydantic: an LLM that
returns malformed or half-invented JSON fails loudly at the boundary, instead
of silently poisoning a report a human later trusts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"

    @property
    def weight(self) -> int:
        return {"critical": 100, "high": 40, "medium": 10, "low": 3, "info": 1}[self.value]


class Category(str, Enum):
    bug = "bug"
    security = "security"
    performance = "performance"
    reliability = "reliability"
    maintainability = "maintainability"
    test_gap = "test_gap"


class Finding(BaseModel):
    """A single defect / risk the analyzer surfaced."""

    title: str = Field(..., min_length=3, max_length=160)
    severity: Severity
    category: Category
    file: str
    line: Optional[int] = Field(default=None, ge=1)
    detail: str = Field(..., min_length=1)
    recommendation: str = Field(default="", description="How to fix it.")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("title", "detail", "recommendation", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class GherkinScenario(BaseModel):
    name: str
    steps: List[str] = Field(default_factory=list)

    def to_feature(self) -> str:
        body = "\n".join(f"    {s}" for s in self.steps)
        return f"  Scenario: {self.name}\n{body}"


class SuggestedTest(BaseModel):
    """A test the LLM proposes to close a coverage gap."""

    title: str
    rationale: str = ""
    target_file: str = ""
    scenario: Optional[GherkinScenario] = None
    pytest_skeleton: str = ""


class FileReport(BaseModel):
    path: str
    language: str = "python"
    findings: List[Finding] = Field(default_factory=list)
    suggested_tests: List[SuggestedTest] = Field(default_factory=list)
    summary: str = ""
    # Set when the file could not be reviewed at all. Without this a provider outage
    # looked identical to a clean file: no findings, gate passes.
    error: str = ""


class Report(BaseModel):
    """The top-level artifact  serialized to JSON and rendered to HTML."""

    project: str = "unknown"
    model: str = "unknown"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    commit: str = ""
    files: List[FileReport] = Field(default_factory=list)
    notes: str = ""

    # ---- derived helpers used by the renderer & the CI gate ----
    @property
    def all_findings(self) -> List[Finding]:
        return [f for fr in self.files for f in fr.findings]

    @property
    def all_tests(self) -> List[SuggestedTest]:
        return [t for fr in self.files for t in fr.suggested_tests]

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.all_findings if f.severity == severity)

    @computed_field
    @property
    def risk_score(self) -> int:
        """Weighted score  the single number a pipeline gate can threshold on."""
        return sum(f.severity.weight for f in self.all_findings)

    @computed_field
    @property
    def severity_breakdown(self) -> dict:
        return {s.value: self.count(s) for s in Severity}

    @property
    def failed_files(self) -> List[FileReport]:
        return [fr for fr in self.files if fr.error]

    @computed_field
    @property
    def reviewed_count(self) -> int:
        return len(self.files) - len(self.failed_files)

    @computed_field
    @property
    def failed_count(self) -> int:
        return len(self.failed_files)

    @computed_field
    @property
    def incomplete(self) -> bool:
        """True when at least one file could not be reviewed."""
        return bool(self.failed_files)

    def gate_fails(self, max_critical: int = 0, max_high: int = 3) -> bool:
        # An incomplete run cannot claim the code is clean.
        if self.files and self.reviewed_count == 0:
            return True
        return self.count(Severity.critical) > max_critical or self.count(Severity.high) > max_high
