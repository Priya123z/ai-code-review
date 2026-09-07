import pytest

from ai_review.providers.base import LLMError, extract_json
from ai_review.providers.openrouter import LLMClient


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_with_prose():
    assert extract_json('Sure! Here it is:\n{"a": 3}\nHope that helps.') == {"a": 3}


def test_extract_json_failure_raises():
    with pytest.raises(LLMError):
        extract_json("no json at all here")


def test_unconfigured_client_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = LLMClient(api_key=None)
    assert client.configured is False
    with pytest.raises(LLMError):
        client.chat("sys", "user")


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("AI_REVIEW_MODEL", "some/model:free")
    assert LLMClient(api_key="k").model == "some/model:free"


def test_explicit_model_beats_the_env_var(monkeypatch):
    # --model used to lose to AI_REVIEW_MODEL, so exporting it silently changed
    # what the command line asked for.
    monkeypatch.setenv("AI_REVIEW_MODEL", "from/env:free")
    assert LLMClient(api_key="k", model="from/flag:free").model == "from/flag:free"


def test_malformed_json_raises_llm_error_not_decode_error():
    # The chain only catches LLMError. A bare JSONDecodeError escaping here skipped
    # the fallback to the next provider entirely.
    with pytest.raises(LLMError):
        extract_json('{"unterminated": ')
