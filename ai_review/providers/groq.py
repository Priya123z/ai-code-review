"""Groq chat client.

Preferred over OpenRouter for the hosted demo: the free tier allows 1000 requests
a day against OpenRouter's 50, it supports a real JSON mode so responses do not
have to be scraped out of prose, and it answers in well under a second.

Free tier limits, which the server's throttle is built around:
    30 requests/min, 1000 requests/day, 8000 tokens/min, 200k tokens/day
Tokens per minute is what actually binds, not request count.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from ai_review.providers.base import BaseClient, LLMError, QuotaExhausted, extract_json

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

# Tried in order when the preferred model is busy.
FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


@dataclass
class GroqClient(BaseClient):
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 90
    max_retries: int = 2

    name: str = field(default="groq", init=False)
    remaining_tokens: Optional[int] = field(default=None, init=False)
    remaining_requests: Optional[int] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL") or self.model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # Groq honours response_format, so with as_json there is nothing to scrape;
    # extract_json still runs above as a cheap guard if a model ignores it.
    def chat(self, system: str, user: str, as_json: bool = False) -> str:
        if not self.configured:
            raise LLMError("GROQ_API_KEY is not set.")

        models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        last_err: Optional[Exception] = None

        for model in models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    return self._post(model, system, user, as_json)
                except QuotaExhausted as exc:
                    # Busy model: move to the next one rather than sleeping out the
                    # request budget on this one.
                    last_err = exc
                    break
                except LLMError as exc:
                    last_err = exc
                    time.sleep(attempt)

        raise QuotaExhausted(f"Groq failed for every model: {last_err}")

    def _post(self, model: str, system: str, user: str, as_json: bool) -> str:
        payload = {
            "model": model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if as_json:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )

        self._record_limits(resp)

        if resp.status_code == 429:
            raise QuotaExhausted(f"Groq rate limited on {model}")

        if resp.status_code >= 400:
            raise LLMError(f"Groq returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if "error" in data:
            raise LLMError(str(data["error"]))

        message = data["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning") or ""

        if not content.strip():
            raise LLMError("empty completion")

        self.model = model
        return content

    def _record_limits(self, resp) -> None:
        # Surfaced on /api/quota so the page can show how many runs are left.
        for header, attribute in [
            ("x-ratelimit-remaining-tokens", "remaining_tokens"),
            ("x-ratelimit-remaining-requests", "remaining_requests"),
        ]:
            value = resp.headers.get(header)
            if value is not None:
                try:
                    setattr(self, attribute, int(value))
                except ValueError:
                    pass
