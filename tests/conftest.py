import json

import pytest

from ai_review.providers.openrouter import LLMClient

FAKE_RESPONSE = {
    "summary": "Handles the happy path but skips validation and edge cases.",
    "findings": [
        {
            "title": "Division by zero on empty cart",
            "severity": "high",
            "category": "bug",
            "line": 25,
            "detail": "average_item_price divides by len(self.items) with no guard.",
            "recommendation": "Return 0 (or raise a domain error) when the cart is empty.",
            "confidence": 0.95,
        },
        {
            "title": "Mutable default argument",
            "severity": "medium",
            "category": "reliability",
            "line": 12,
            "detail": "items=[] is shared across instances.",
            "recommendation": "Default to None and create a new list inside __init__.",
            "confidence": 0.9,
        },
    ],
    "suggested_tests": [
        {
            "title": "Empty cart average is safe",
            "rationale": "Guards the div-by-zero path.",
            "scenario": {
                "name": "Average price of an empty cart",
                "steps": ["Given an empty cart", "When I request the average price", "Then it returns 0 without error"],
            },
            "pytest_skeleton": "def test_empty_cart_average():\n    assert ShoppingCart([]).average_item_price() == 0",
        }
    ],
}


class FakeClient(LLMClient):
    """Drop-in LLMClient that never touches the network."""

    def __init__(self, payload=None, **kw):
        super().__init__(api_key="test-key", **kw)
        self._payload = payload if payload is not None else FAKE_RESPONSE

    def chat(self, system, user, as_json=False):  # noqa: D401
        return "```json\n" + json.dumps(self._payload) + "\n```"


@pytest.fixture
def fake_client():
    return FakeClient()
