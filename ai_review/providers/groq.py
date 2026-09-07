"""Groq chat client.

Preferred over OpenRouter for the hosted demo: the free tier allows 1000 requests
a day against OpenRouter's 50, it supports a real JSON mode so responses do not
have to be scraped out of prose, and it answers in well under a second.

Free tier limits, for anyone budgeting against them:
    30 requests/min, 1000 requests/day, 8000 tokens/min, 200k tokens/day
Tokens per minute is what actually binds, not request count.
"""
import os
import time

import requests

from ai_review.providers.base import BaseClient, LLMError, QuotaExhausted

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

# Tried in order when the preferred model is busy.
FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


class GroqClient(BaseClient):
    name = "groq"

    def __init__(self, api_key=None, model=DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL") or model
        self.temperature = 0.1
        self.max_tokens = 2000
        self.timeout = 90
        self.max_retries = 2

    @property
    def configured(self):
        return bool(self.api_key)

    # Groq honours response_format, so with as_json there is nothing to scrape.
    # BaseClient.chat_json still runs extract_json over the result, as a cheap
    # guard for the day a model ignores it.
    def chat(self, system, user, as_json=False):
        if not self.configured:
            raise LLMError("GROQ_API_KEY is not set.")

        models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        last_err = None

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

    def _post(self, model, system, user, as_json):
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
