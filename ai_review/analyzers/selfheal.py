"""Self-healing locators.

When a UI test fails because a selector no longer matches, the fix is usually
mechanical: the element is still on the page, just addressed differently. This
asks the model to repair a broken selector against the *current* DOM and return
a resilient, Playwright-ready locator, preferring role, text and test-id over a
brittle CSS path.

Scoped to one step on purpose. "Self-healing tests" usually means a suite that
rewrites itself, which hides the fact that the page changed. This suggests a
locator and stops; the engineer still reads it and commits it.
"""
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


FIELDS = ("found", "strategy", "locator", "playwright", "confidence", "reasoning")


def _result(found=False, strategy="css", locator="", playwright="", confidence=0.0, reasoning=""):
    try:
        confidence = min(1.0, max(0.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "found": bool(found),
        "strategy": str(strategy or "css"),
        "locator": str(locator or ""),
        "playwright": str(playwright or ""),
        "confidence": confidence,
        "reasoning": str(reasoning or ""),
    }


def heal_locator(client, selector, html, description=""):
    data = client.chat_json(
        SYSTEM,
        USER_TEMPLATE.format(
            selector=selector, description=description or "(not specified)", html=html[:8000]
        ),
    )
    try:
        return _result(**{k: v for k, v in data.items() if k in FIELDS})
    except Exception:
        return _result(reasoning="Model returned an unparseable suggestion.")
