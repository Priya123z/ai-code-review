"""Try providers in order until one answers.

The free tiers this runs on are small and go quiet without warning, so two of the
OpenRouter free models returned 429 on the very first call while this was being
built. A single provider is not enough to keep a public demo working, so the
chain falls through Groq to OpenRouter and reports which one actually served the
request.
"""
from ai_review.providers.base import BaseClient, LLMError, QuotaExhausted
from ai_review.providers.groq import GroqClient
from ai_review.providers.openrouter import LLMClient


class FallbackClient(BaseClient):
    def __init__(self, clients):
        self.clients = [c for c in clients if c.configured]
        self.served_by = None
        self._served = None

    @property
    def configured(self):
        return bool(self.clients)

    @property
    def model(self):
        # The provider that answered, not the one we tried first.
        client = self._served or (self.clients[0] if self.clients else None)
        return client.model if client else ""

    def chat(self, system, user, as_json=False):
        return self._through(lambda c: c.chat(system, user, as_json=as_json))

    def chat_json(self, system, user):
        return self._through(lambda c: c.chat_json(system, user))

    def _through(self, call):
        if not self.clients:
            raise LLMError(
                "No provider is configured. Set GROQ_API_KEY or OPENROUTER_API_KEY."
            )

        errors = []
        for client in self.clients:
            try:
                result = call(client)
                self.served_by = client.name
                self._served = client
                return result
            except QuotaExhausted as exc:
                errors.append(f"{client.name}: {exc}")
            except LLMError as exc:
                errors.append(f"{client.name}: {exc}")

        raise QuotaExhausted("every provider failed. " + "; ".join(errors))


def build_client(api_key=None, model=None):
    """Groq first, OpenRouter behind it.

    A caller-supplied key is treated as a Groq key.
    """
    if api_key:
        groq = GroqClient(api_key=api_key)
        if model:
            groq.model = model
        return FallbackClient([groq])

    groq = GroqClient()
    openrouter = LLMClient()

    # A model slug belongs to one provider, so only override the one it came from.
    # Passing an OpenRouter slug to Groq just made Groq fall back to another model.
    if model:
        if "/" in model and model.endswith(":free"):
            openrouter.model = model
        else:
            groq.model = model

    return FallbackClient([groq, openrouter])
