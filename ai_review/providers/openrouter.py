"""OpenRouter chat client, used as the fallback behind Groq.

The free tier here is thin  50 requests a day on an unfunded account, 20 a
minute  so this is not the first choice for anything public. Paid model slugs
are avoided by default because a zero-balance account starts returning 402.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from ai_review.providers.base import (  # noqa: F401 - re-exported for callers
    BaseClient,
    LLMError,
    QuotaExhausted,
    extract_json,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# A free slug, so this keeps working on an account with no credit.
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

FALLBACK_MODELS = ["cohere/north-mini-code:free", "google/gemma-4-31b-it:free"]


@dataclass
class LLMClient(BaseClient):
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 3000
    timeout: int = 90
    max_retries: int = 2

    name: str = field(default="openrouter", init=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        # An explicit model argument wins. This used to be the other way round, so
        # exporting AI_REVIEW_MODEL silently overrode --model on the command line.
        if self.model == DEFAULT_MODEL:
            self.model = os.getenv("AI_REVIEW_MODEL", self.model)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, as_json: bool = False) -> str:
        if not self.configured:
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Export it locally or add it as a "
                "GitHub Actions secret named OPENROUTER_API_KEY."
            )

        models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        last_err: Optional[Exception] = None

        for model in models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    return self._post(model, system, user, as_json)
                except QuotaExhausted as exc:
                    last_err = exc
                    break
                except Exception as exc:  # noqa: BLE001 - retry any transient failure
                    last_err = exc
                    time.sleep(1.5 * attempt)

        raise QuotaExhausted(f"OpenRouter failed for every model: {last_err}")

    def _post(self, model: str, system: str, user: str, as_json: bool = False) -> str:
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Priya123z/ai-code-review",
            "X-Title": "ai-code-review",
        }

        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=self.timeout)

        if resp.status_code in (402, 429):
            raise QuotaExhausted(f"OpenRouter returned {resp.status_code} for {model}")

        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise LLMError(str(data["error"]))

        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""

        # Reasoning models put their working in `reasoning` and the answer in `content`.
        # Falling back to `reasoning` when asking for JSON just hands back the model
        # thinking out loud, which never parses. Better to fail and try the next model.
        if not content.strip() and not as_json:
            content = msg.get("reasoning") or ""

        if not content.strip():
            raise LLMError(f"{model} returned no content")

        self.model = model
        return content
