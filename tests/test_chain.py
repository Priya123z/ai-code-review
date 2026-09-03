import pytest

from ai_review.providers.base import BaseClient, LLMError, QuotaExhausted
from ai_review.providers.chain import FallbackClient, build_client


class Stub(BaseClient):
    def __init__(self, name, answer=None, raises=None, configured=True):
        self.name = name
        self.model = f"{name}/model"
        self._answer = answer
        self._raises = raises
        self._configured = configured
        self.calls = 0

    @property
    def configured(self):
        return self._configured

    def chat_json(self, system, user):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._answer


def test_first_healthy_provider_answers():
    first = Stub("groq", answer={"ok": 1})
    second = Stub("openrouter", answer={"ok": 2})

    chain = FallbackClient([first, second])

    assert chain.chat_json("s", "u") == {"ok": 1}
    assert chain.served_by == "groq"
    assert second.calls == 0


def test_falls_through_when_the_first_is_rate_limited():
    first = Stub("groq", raises=QuotaExhausted("429"))
    second = Stub("openrouter", answer={"ok": 2})

    chain = FallbackClient([first, second])

    assert chain.chat_json("s", "u") == {"ok": 2}
    assert chain.served_by == "openrouter"


def test_unconfigured_providers_are_skipped():
    chain = FallbackClient([Stub("groq", configured=False), Stub("openrouter", answer={"ok": 3})])

    assert [c.name for c in chain.clients] == ["openrouter"]
    assert chain.chat_json("s", "u") == {"ok": 3}


def test_exhausting_every_provider_raises_quota_exhausted():
    chain = FallbackClient([
        Stub("groq", raises=QuotaExhausted("429")),
        Stub("openrouter", raises=LLMError("boom")),
    ])

    with pytest.raises(QuotaExhausted) as excinfo:
        chain.chat_json("s", "u")

    assert "groq" in str(excinfo.value)
    assert "openrouter" in str(excinfo.value)


def test_no_providers_at_all_is_a_clear_error():
    chain = FallbackClient([])

    assert chain.configured is False
    with pytest.raises(LLMError, match="No provider is configured"):
        chain.chat_json("s", "u")


def test_a_supplied_key_is_used_on_its_own(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "server-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-key")

    chain = build_client(api_key="visitor-key")

    assert [c.name for c in chain.clients] == ["groq"]
    assert chain.clients[0].api_key == "visitor-key"


def test_build_client_prefers_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")

    assert [c.name for c in build_client().clients] == ["groq", "openrouter"]


def test_build_client_without_groq_still_works(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")

    assert [c.name for c in build_client().clients] == ["openrouter"]


def test_model_reflects_the_provider_that_answered():
    first = Stub("groq", raises=QuotaExhausted("429"))
    second = Stub("openrouter", answer={"ok": 1})

    chain = FallbackClient([first, second])
    chain.chat_json("s", "u")

    assert chain.model == "openrouter/model"


def test_chat_json_goes_through_chat():
    # The whole suite runs offline by substituting chat(). If chat_json ever calls the
    # transport directly again, every fake in the test suite is silently bypassed.
    class OnlyChat(BaseClient):
        name = "onlychat"
        model = "m"
        configured = True

        def chat(self, system, user, as_json=False):
            assert as_json is True
            return '{"routed": true}'

    assert OnlyChat().chat_json("s", "u") == {"routed": True}
