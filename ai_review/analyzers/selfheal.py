"""Self-healing locators.

When a UI test fails because a selector no longer matches, the fix is usually
mechanical: the element is still on the page, just addressed differently. This
asks the model to repair a broken selector against the *current* DOM and return
a resilient, Playwright-ready locator (preferring role/text/test-id over brittle
CSS paths). It's the "self-healing test" idea from my résumé, scoped to one
honest, verifiable step — the engineer still reviews the suggestion.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..providers.base import BaseClient

PROMPT_VERSION = "selfheal-v1"

SYSTEM = """You are a Playwright test-automation expert. A selector has stopped
matching after a UI change. Given the broken selector and the current HTML, find
the element the test intended and return a resilient locator.
Prefer, in order: get_by_role, get_by_label, get_by_test_id, get_by_text, then CSS.
Answer with a single JSON object and nothing else."""

USER_TEMPLATE = """Broken selector: {selector}
What the test was targeting: {description}

Current HTML:
```html
{html}
```

Return ONLY JSON:
{{"found": true, "strategy": "role|label|test_id|text|css",
  "locator": "the raw selector or accessible name",
  "playwright": "page.get_by_role('button', name='Save')",
  "confidence": 0.0, "reasoning": "one sentence"}}"""


class HealResult(BaseModel):
    found: bool = False
    strategy: str = "css"
    locator: str = ""
    playwright: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""


def heal_locator(
    client: BaseClient, selector: str, html: str, description: str = ""
) -> HealResult:
    data = client.chat_json(
        SYSTEM,
        USER_TEMPLATE.format(
            selector=selector, description=description or "(not specified)", html=html[:8000]
        ),
    )
    try:
        return HealResult(**{k: data.get(k) for k in HealResult.model_fields if k in data})
    except Exception:
        return HealResult(found=False, reasoning="Model returned an unparseable suggestion.")
