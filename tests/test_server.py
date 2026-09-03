"""The demo runs on a free tier, so the interesting behaviour is what happens when
the budget is gone. None of these tests touch the network."""

import pytest
from fastapi.testclient import TestClient

from ai_review.providers.base import BaseClient, LLMError, QuotaExhausted
from server import app as app_module
from server.app import app
from server.cache import ResponseCache
from server.quota import Quota, estimate_tokens

FINDING = {
    "findings": [
        {"title": "Division by zero", "severity": "high", "category": "bug", "line": 2,
         "confidence": 0.9, "detail": "len(items) can be 0", "recommendation": "guard it"}
    ],
    "suggested_tests": [],
    "summary": "one issue",
}


class Fake(BaseClient):
    name = "fake"
    model = "fake/model"
    configured = True

    def __init__(self, raises=None):
        self._raises = raises
        self.calls = 0

    def chat(self, system, user, as_json=False):
        self.calls += 1
        if self._raises:
            raise self._raises
        import json
        return json.dumps(FINDING)


@pytest.fixture
def client(monkeypatch):
    # Fresh budget and cache per test, otherwise they leak between them.
    monkeypatch.setattr(app_module, "quota", Quota())
    monkeypatch.setattr(app_module, "cache", ResponseCache())
    return TestClient(app)


def use(monkeypatch, fake):
    monkeypatch.setattr(app_module, "build_client", lambda api_key=None: fake)


def post_review(client, code="def f():\n    pass\n"):
    return client.post("/api/review", json={"code": code})


def test_a_live_answer_reports_its_provider(client, monkeypatch):
    use(monkeypatch, Fake())

    body = post_review(client).json()

    assert body["meta"]["source"] == "live"
    assert body["meta"]["provider"] == "fake"
    assert body["result"]["findings"][0]["title"] == "Division by zero"


def test_the_same_input_twice_only_calls_the_model_once(client, monkeypatch):
    fake = Fake()
    use(monkeypatch, fake)

    post_review(client)
    second = post_review(client).json()

    assert second["meta"]["source"] == "cache"
    assert fake.calls == 1


def test_running_out_of_quota_serves_a_cached_example_not_an_error(client, monkeypatch):
    use(monkeypatch, Fake())
    monkeypatch.setattr(app_module, "quota", Quota(per_visitor_per_day=0))

    response = post_review(client)

    # A recruiter clicking a dead demo learns nothing, so this must still be a 200
    # with real content, clearly labelled as not live.
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["source"] == "cached"
    assert body["meta"]["reason"] == "visitor_daily"
    assert body["result"]["findings"]


def test_a_dead_provider_also_serves_the_cached_example(client, monkeypatch):
    use(monkeypatch, Fake(raises=QuotaExhausted("429 everywhere")))

    body = post_review(client).json()

    assert body["meta"]["source"] == "cached"
    assert body["meta"]["reason"] == "provider_unavailable"


def test_a_provider_error_is_distinguished_from_being_rate_limited(client, monkeypatch):
    use(monkeypatch, Fake(raises=LLMError("bad json")))

    assert post_review(client).json()["meta"]["reason"] == "provider_error"


def test_your_own_key_skips_the_shared_budget(client, monkeypatch):
    use(monkeypatch, Fake())
    monkeypatch.setattr(app_module, "quota", Quota(per_visitor_per_day=0))

    body = client.post("/api/review", json={"code": "x = 1"}, headers={"X-API-Key": "mine"}).json()

    assert body["meta"]["source"] == "live"


def test_long_input_is_truncated_before_it_reaches_the_model(client, monkeypatch):
    captured = {}

    class Capturing(Fake):
        def chat(self, system, user, as_json=False):
            captured["length"] = len(user)
            return super().chat(system, user, as_json)

    use(monkeypatch, Capturing())
    post_review(client, code="x = 1\n" * 20_000)

    assert captured["length"] < 20_000


def test_quota_reports_what_is_left(client):
    before = client.get("/api/quota").json()

    assert before["your_runs_remaining_today"] > 0
    assert before["tokens_remaining_today"] > 0


def test_a_run_is_only_charged_once(client, monkeypatch):
    use(monkeypatch, Fake())

    post_review(client)
    after_first = client.get("/api/quota").json()["your_runs_remaining_today"]

    post_review(client)  # cache hit, must not be charged again
    after_cached = client.get("/api/quota").json()["your_runs_remaining_today"]

    assert after_cached == after_first


def test_health_lists_providers(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_empty_input_is_rejected(client):
    assert client.post("/api/review", json={"code": ""}).status_code == 422


class TestTokenBudget:
    def test_a_big_request_is_refused_before_it_is_sent(self):
        quota = Quota(tokens_per_minute=1000)

        assert quota.check("ip", 5000).allowed is False

    def test_refusal_says_how_long_to_wait(self):
        quota = Quota(tokens_per_minute=1000)
        quota.record("ip", 900)

        decision = quota.check("ip", 500)

        assert decision.allowed is False
        assert 0 < decision.retry_after <= 61

    def test_one_visitor_cannot_drain_the_day(self):
        quota = Quota(per_visitor_per_day=2)

        for _ in range(2):
            assert quota.check("ip", 10).allowed
            quota.record("ip", 10)

        assert quota.check("ip", 10).allowed is False
        # someone else is unaffected
        assert quota.check("other", 10).allowed is True

    def test_estimate_grows_with_input(self):
        assert estimate_tokens("x" * 4000) > estimate_tokens("x" * 40)
