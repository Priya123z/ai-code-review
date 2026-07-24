"""Thin, dependency-light OpenRouter chat client.

Isolated behind one class so the rest of the pipeline never touches HTTP.
That boundary is also what makes the whole suite testable with no API key —
tests inject a fake ``chat`` and the pipeline never knows the difference.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Proven working with a free-tier key. Override with AIQA_MODEL.
# Free alternatives (may rate-limit): openai/gpt-oss-20b:free,
# nvidia/nemotron-3-super-120b-a12b:free, google/gemma-4-31b-it:free
DEFAULT_MODEL = "deepseek/deepseek-chat-v3.1"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMClient:
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 90
    max_retries: int = 3

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("AIQA_MODEL", self.model)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str) -> str:
        """Return raw assistant text for a system+user turn."""
        if not self.configured:
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Export it locally or add it as a "
                "GitHub Actions secret named OPENROUTER_API_KEY."
            )
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Priya123z/AI-pipeline-report",
            "X-Title": "aiqa",
        }
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code == 429:
                    time.sleep(2 * attempt)
                    last_err = LLMError("rate limited (429)")
                    continue
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise LLMError(str(data["error"]))
                msg = data["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning") or ""
                if not content.strip():
                    raise LLMError("empty completion")
                return content
            except Exception as exc:  # noqa: BLE001 - retry any transient failure
                last_err = exc
                time.sleep(1.5 * attempt)
        raise LLMError(f"LLM call failed after {self.max_retries} attempts: {last_err}")

    def chat_json(self, system: str, user: str) -> dict:
        """Return the assistant turn parsed as JSON, tolerating code fences."""
        raw = self.chat(system, user)
        return extract_json(raw)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction — handles fenced blocks and leading prose."""
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
        return json.loads(text[start : end + 1])
    raise LLMError(f"Could not parse JSON from model output: {text[:200]}...")
