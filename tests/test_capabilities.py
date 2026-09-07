"""Tests for the RAG-context, self-heal, and test-emit capabilities (mocked)."""
import os

from ai_review.analyzers.context import build_repo_context
from ai_review.analyzers.selfheal import heal_locator
from ai_review.core.collector import SourceFile
from ai_review.report.emit import emit_tests
from ai_review.report import schema
from tests.conftest import FakeClient


def _sources():
    return [
        SourceFile(path="auth.py", abspath="/x/auth.py",
                   content="def login(u, p):\n    return None\nclass Session:\n    pass\n"),
        SourceFile(path="pay.py", abspath="/x/pay.py",
                   content="def charge(amount):\n    return amount\n"),
    ]


def test_repo_context_lists_sibling_signatures_and_skips_self():
    ctx = build_repo_context(_sources(), skip_path="pay.py")
    assert "auth.py" in ctx and "def login" in ctx and "class Session" in ctx
    assert "def charge" not in ctx  # pay.py was skipped


def test_self_heal_returns_structured_locator():
    payload = {"found": True, "strategy": "role", "locator": "Save",
               "playwright": "page.get_by_role('button', name='Save')",
               "confidence": 0.9, "reasoning": "Button text is stable."}
    client = FakeClient(payload=payload)
    res = heal_locator(client, "#save-btn-old", "<button>Save</button>", "the save button")
    assert res["found"] and res["strategy"] == "role"
    assert "get_by_role" in res["playwright"]


def test_emit_tests_writes_feature_and_pytest(tmp_path):
    report = schema.report(files=[schema.file_report("cart.py", suggested_tests=[
        schema.suggested_test(title="empty cart",
                              pytest_skeleton="def test_empty():\n    assert True",
                              scenario=schema.scenario("Empty cart", ["Given a cart", "Then ok"]))
    ])])
    counts = emit_tests(report, str(tmp_path))
    assert counts == {"features": 1, "pytest_modules": 1}
    assert os.path.exists(tmp_path / "cart.feature")
    assert "def test_empty" in open(tmp_path / "test_cart.py").read()
