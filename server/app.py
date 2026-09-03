"""HTTP API behind the demos on the portfolio site.

Three things matter here beyond calling a model:

  - it runs on a free tier, so requests are budgeted by token count, not just by
    request count, and a visitor can bring their own key to skip the budget
  - when the budget is gone it answers with a cached example rather than a 500,
    clearly labelled, because a recruiter clicking a dead demo learns nothing
  - the provider that served the answer is reported back, so the fallback is
    visible rather than magic
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai_review.analyzers.defects import analyze_file
from ai_review.analyzers.selfheal import heal_locator
from ai_review.analyzers.specs import generate_specs
from ai_review.core.collector import SourceFile
from ai_review.providers.base import LLMError, QuotaExhausted
from ai_review.providers.chain import build_client
from server.cache import ResponseCache
from server.quota import Quota, estimate_tokens

MAX_INPUT_CHARS = 6000

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://priya123z.github.io,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if o.strip()
]

SAMPLES = pathlib.Path(__file__).parent / "samples"

app = FastAPI(title="ai-review demo API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

quota = Quota()
cache = ResponseCache()


class ReviewRequest(BaseModel):
    code: str = Field(min_length=1)
    filename: str = "snippet.py"
    language: str = "python"


class SpecsRequest(BaseModel):
    story: str = Field(min_length=1)


class HealRequest(BaseModel):
    selector: str = Field(min_length=1)
    html: str = Field(min_length=1)
    description: str = ""


def visitor_of(request: Request) -> str:
    # Spaces sit behind a proxy, so the socket address is the proxy, not the caller.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def sample(name: str) -> Optional[dict]:
    path = SAMPLES / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def cached_reply(name: str, reason: str, retry_after: int = 0) -> JSONResponse:
    """Serve a pre-generated example instead of an error.

    Labelled `cached`, so the page can say so rather than passing it off as live.
    """
    body = sample(name)
    if body is None:
        return JSONResponse(
            {"error": "The demo is out of quota. Try again later or use your own key."},
            status_code=503,
        )

    return JSONResponse(
        {
            "result": body,
            "meta": {"source": "cached", "reason": reason, "retry_after": retry_after},
        },
        status_code=200,
    )


def run(name: str, key: Optional[str], visitor: str, text: str, work):
    """Cache, budget, call, fall back. Shared by all three endpoints."""
    own_key = bool(key)

    cache_key = ResponseCache.key(name, text, "byok" if own_key else "shared")
    hit = cache.get(cache_key)
    if hit is not None:
        return {"result": hit, "meta": {"source": "cache", "provider": None}}

    if not own_key:
        decision = quota.check(visitor, estimate_tokens(text))
        if not decision.allowed:
            return cached_reply(name, decision.reason, decision.retry_after)

    client = build_client(api_key=key)
    if not client.configured:
        return cached_reply(name, "no_provider")

    try:
        result = work(client)
    except (QuotaExhausted, LLMError) as exc:
        return cached_reply(name, "provider_unavailable" if isinstance(exc, QuotaExhausted) else "provider_error")

    if not own_key:
        quota.record(visitor, estimate_tokens(text))

    cache.put(cache_key, result)
    return {"result": result, "meta": {"source": "live", "provider": client.served_by or client.name, "model": client.model}}


@app.get("/api/health")
def health():
    return {"status": "ok", "providers": [c.name for c in build_client().clients]}


@app.get("/api/quota")
def quota_status(request: Request):
    return {**quota.snapshot(visitor_of(request)), "cache": cache.stats()}


@app.post("/api/review")
def review(body: ReviewRequest, request: Request, x_api_key: Optional[str] = Header(None)):
    code = body.code[:MAX_INPUT_CHARS]

    def work(client):
        source = SourceFile(
            path=body.filename, abspath=body.filename, content=code, language=body.language
        )
        return analyze_file(client, source).model_dump()

    return run("review", x_api_key, visitor_of(request), code, work)


@app.post("/api/specs")
def specs(body: SpecsRequest, request: Request, x_api_key: Optional[str] = Header(None)):
    story = body.story[:MAX_INPUT_CHARS]
    work = lambda client: generate_specs(client, story).model_dump()
    return run("specs", x_api_key, visitor_of(request), story, work)


@app.post("/api/heal")
def heal(body: HealRequest, request: Request, x_api_key: Optional[str] = Header(None)):
    html = body.html[:MAX_INPUT_CHARS]
    work = lambda client: heal_locator(client, body.selector, html, body.description).model_dump()
    return run("heal", x_api_key, visitor_of(request), body.selector + html, work)
