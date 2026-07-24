import pytest

from aiqa.providers.openrouter import LLMClient, LLMError, extract_json


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
    monkeypatch.setenv("AIQA_MODEL", "some/model:free")
    assert LLMClient(api_key="k").model == "some/model:free"
