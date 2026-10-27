#!/usr/bin/env python3
"""Guthrie as a standalone HTTP service.

Wraps the guthrie skill's retrieval brain (kernel.py) behind a small FastAPI app.
Its one caller is the Phebe API, which asks on behalf of a signed-in Phebe
member (the chat page is app.phebe.life/guthrie). This calls kernel.pku_ask
itself (not a copy) and only injects the grounding LLM via the Anthropic API
(the skill's host.llm is not present outside Claude Science), so the refusal
gate, medical flag, and citation logic are literally the same code the eval
scored.

    ANTHROPIC_API_KEY=sk-...  GUTHRIE_API_TOKEN=...  GUTHRIE_INDEX_DIR=./pku_index  uvicorn serve:app

Endpoints:
    GET  /health        -> {status, n_chunks, index_version, answer_model}
    POST /api/ask       {question}               -> {answer, citations, hits, refused, medical_flag}
    POST /api/search    {query, k?, source?}     -> [{citation, title, score, url, ...}]

The answer contract is identical to the skill: cite-or-refuse, medical-advice
flag + clinician deferral, off-topic refusal. This is the same code path the
eval scored, so the number on the website is the number in eval/report.md.
"""
import hmac
import os
import sys
import time
from collections import deque

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# import the skill's retrieval brain (kernel.py sits one dir up)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kernel  # noqa: E402

# Current, live Haiku snapshot. The dated 3.5 snapshots get retired by Anthropic
# over time (a retired id returns HTTP 404) — the same failure that took the chat
# agent down — so default to the current generation. Override per-deploy with
# GUTHRIE_ANSWER_MODEL. The scored gate (refusal, citations, medical flag) lives
# in kernel.py, not the LLM; the model only phrases the grounded answer.
ANSWER_MODEL = os.environ.get("GUTHRIE_ANSWER_MODEL", "claude-haiku-4-5-20251001")

# Every answer is a paid Anthropic call, and only members may ask. The Phebe
# API checks the member's session and limits each member; it then calls here
# with this shared secret. There is no browser caller, so no CORS and no
# Turnstile: a request without the secret is refused, and with no secret
# configured every /api/* request is refused (fail closed).
API_TOKEN = os.environ.get("GUTHRIE_API_TOKEN", "").strip()
if not API_TOKEN:
    print("[auth] GUTHRIE_API_TOKEN is not set: /api/* refuses every request", flush=True)

# A ceiling on answers per minute across all members, in case the secret ever
# leaks. Members' own limits live in the Phebe API. One Railway replica runs
# this process, so an in-memory counter is effective. Counted after the secret
# is checked, so strangers cannot use up the members' allowance.
RATE_LIMIT_MAX = int(os.environ.get("GUTHRIE_RATE_LIMIT_PER_MIN", "60"))
RATE_LIMIT_WINDOW = 60.0
_rl_hits: deque = deque()

# No /docs, /redoc or /openapi.json: nobody but the Phebe API calls this.
app = FastAPI(title="Guthrie - PKU research agent", version="0", docs_url=None, redoc_url=None, openapi_url=None)


def require_token(authorization: str | None = Header(default=None)):
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {API_TOKEN}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


def rate_limit(_=Depends(require_token)):
    now = time.monotonic()
    while _rl_hits and now - _rl_hits[0] > RATE_LIMIT_WINDOW:
        _rl_hits.popleft()
    if len(_rl_hits) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    _rl_hits.append(now)


# A question is the question and nothing else: how many passages to read, the
# answer length and the relevance floor are the server's choice, so no caller
# can make a call cost more or skip the off-topic refusal.
ASK_K = 8
ASK_MODE = "brief"


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=8, ge=1, le=20)
    source: str | None = Field(default=None, max_length=64)


def _anthropic_llm(prompt, system, max_tokens):
    """The grounding call, via the Anthropic API (stands in for host.llm)."""
    import anthropic
    # Reads ANTHROPIC_API_KEY. A short timeout and one retry: the SDK's default
    # waits up to 10 minutes, holding a worker thread the whole time.
    client = anthropic.Anthropic(timeout=30.0, max_retries=1)
    msg = client.messages.create(
        model=ANSWER_MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}])
    return {"text": "".join(b.text for b in msg.content if b.type == "text")}


@app.get("/health")
def health():
    info = kernel.guthrie_index_info()
    return {"status": "ok", "n_chunks": info["n_chunks"],
            "index_version": info["version"], "answer_model": ANSWER_MODEL}


@app.post("/api/ask")
def ask(body: AskBody, _=Depends(rate_limit)):
    # SAME code path as the skill + eval: kernel.pku_ask owns the refusal gate,
    # medical flag, and citation logic. We only inject the grounding LLM.
    r = kernel.pku_ask(body.question, k=ASK_K, mode=ASK_MODE,
                       min_relevance=kernel.DEFAULT_MIN_RELEVANCE, llm=_anthropic_llm)
    # trim hit payload for the wire (drop full passage text)
    r["hits"] = [{"citation": h["citation"], "title": h["title"],
                  "url": h["url"], "source": h["source"],
                  "score": h["score"]} for h in r["hits"]]
    return r


@app.post("/api/search")
def search(body: SearchBody, _=Depends(require_token)):
    hits = kernel.pku_search(body.query, k=body.k, source=body.source)
    return [{"citation": h["citation"], "title": h["title"], "url": h["url"],
             "source": h["source"], "year": h["year"], "score": h["score"]}
            for h in hits]
