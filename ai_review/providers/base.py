"""Shared pieces for the chat providers.

Everything above this layer talks to `chat` / `chat_json` and never touches HTTP,
which is what lets the whole suite run with no API key.
"""
import json
import re


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """The provider is rate limited or out of quota. Worth trying the next one."""


class BaseClient:
    name = "base"
    model = ""
    # Which provider actually answered. Only the fallback chain has a choice to make;
    # for a single client it is just itself. Declared here so callers can read it off
    # any client without knowing which kind they hold.
    served_by = None

    @property
    def configured(self):
        raise NotImplementedError

    def chat(self, system, user, as_json=False):
        raise NotImplementedError

    def chat_json(self, system, user):
        return extract_json(self.chat(system, user, as_json=True))


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text):
    """Best-effort JSON extraction, handling fenced blocks and leading prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    # Always an LLMError, never a bare JSONDecodeError. A decode error escaping this
    # function skipped past the provider fallback, because the chain only catches
    # LLMError, and surfaced as an unreviewed file instead of trying the next provider.
    raise LLMError(f"Could not parse JSON from model output: {text[:200]}...")
