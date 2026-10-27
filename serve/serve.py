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
    GET  /health        -> {status, n_chunks, index_version, answer_model, answers}
    POST /api/ask       {question}               -> {answer, citations, hits, refused, medical_flag}
    POST /api/search    {query, k?, source?, slices?} -> [{citation, title, score, url, ...}]
    POST /api/paper     {ref, max_chars?}        -> one paper: full text if open access, else abstract
    GET  /api/concerns  -> [{key, label, papers}] the literature slices (PKU, pterin)

The answer writer is chosen by environment:
    ANTHROPIC_API_KEY set     -> Anthropic API (GUTHRIE_ANSWER_MODEL); production
    GUTHRIE_OLLAMA_MODEL set  -> a local model through Ollama (GUTHRIE_OLLAMA_URL)
    GUTHRIE_ANSWERS=extractive -> no model: one lead sentence per source, cited
    none of these             -> answer=null with the ranked sources

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
    slices: list[str] | None = Field(default=None, max_length=8)


class PaperBody(BaseModel):
    ref: str = Field(min_length=1, max_length=200)
    max_chars: int = Field(default=60000, ge=0, le=400000)


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


OLLAMA_MODEL = os.environ.get("GUTHRIE_OLLAMA_MODEL", "").strip()
OLLAMA_URL = os.environ.get("GUTHRIE_OLLAMA_URL", "http://localhost:11434")


def _ollama_llm(prompt, system, max_tokens):
    """The grounding call through a local Ollama model (no key, no network)."""
    import json as _json
    import urllib.request
    body = _json.dumps({"model": OLLAMA_MODEL, "system": system, "prompt": prompt, "stream": False,
                        "options": {"num_predict": max_tokens}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return {"text": _json.load(r).get("response", "")}


def _extractive_llm(prompt, system, max_tokens):
    """No model at all: one lead sentence per retrieved passage, cited. The
    passages arrive in the prompt as '[LABEL] (source, year) Title\n<text>'."""
    import re as _re
    blocks = prompt.split("CONTEXT (each passage is prefixed with its citation label):", 1)[-1]
    blocks = blocks.split("\n\nQUESTION:", 1)[0]
    out, seen = [], set()
    for block in blocks.split("\n\n---\n\n"):
        m = _re.match(r"\s*\[([^\]]+)\][^\n]*\n(.*)", block, _re.S)
        if not m:
            continue
        label, text = m.group(1), m.group(2)
        if label in seen:
            continue
        seen.add(label)
        body = text.split("\n\n", 1)[-1] if "\n\n" in text else text
        body = _re.sub(r"^(BACKGROUND|INTRODUCTION|OBJECTIVES?|AIMS?|PURPOSE|METHODS?|RESULTS?|CONCLUSIONS?|FINDINGS|DESIGN|SETTING|PARTICIPANTS):\s*", "", body.strip(), flags=_re.I)
        # prefer a results or conclusion sentence when the abstract is structured
        rc = _re.search(r"(?:RESULTS?|CONCLUSIONS?|FINDINGS):\s*([^.]{30,}\.)", text, _re.I)
        sent = rc.group(1) if rc else _re.split(r"(?<=[.!?])\s+", body)[0]
        if sent:
            out.append(f"{sent.strip()} [{label}]")
        if len(out) >= 6:
            break
    return {"text": "What the sources report:\n\n" + "\n\n".join(out) if out else ""}


def _llm():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic_llm
    if OLLAMA_MODEL:
        return _ollama_llm
    if os.environ.get("GUTHRIE_ANSWERS") == "extractive":
        return _extractive_llm
    return None


def _answers():
    llm = _llm()
    return {_anthropic_llm: "anthropic", _ollama_llm: "ollama",
            _extractive_llm: "extractive"}.get(llm, "none")


@app.get("/health")
def health():
    info = kernel.guthrie_index_info()
    return {"status": "ok", "n_chunks": info["n_chunks"],
            "index_version": info["version"], "answer_model": ANSWER_MODEL,
            "answers": _answers()}


@app.post("/api/ask")
def ask(body: AskBody, _=Depends(rate_limit)):
    # SAME code path as the skill + eval: kernel.pku_ask owns the refusal gate,
    # medical flag, and citation logic. We only inject the grounding LLM.
    r = kernel.pku_ask(body.question, k=ASK_K, mode=ASK_MODE,
                       min_relevance=kernel.DEFAULT_MIN_RELEVANCE, llm=_llm())
    # Trim the hits for the wire (no passage text), one row per paper. A paper
    # can come back as its abstract and as full-text sections; the row carries
    # the paper's own title, not a section's.
    seen, hits = set(), []
    for h in r["hits"]:
        if h["citation"] in seen:
            continue
        seen.add(h["citation"])
        hits.append({"citation": h["citation"], "title": h["paper_title"],
                     "url": h["url"], "source": h["source"], "year": h["year"],
                     "slice": h.get("slice") or "", "score": h["score"]})
    r["hits"] = hits
    return r


@app.post("/api/search")
def search(body: SearchBody, _=Depends(require_token)):
    hits = kernel.pku_search(body.query, k=body.k, source=body.source, slices=body.slices)
    return [{"citation": h["citation"], "title": h["title"], "url": h["url"],
             "source": h["source"], "year": h["year"], "score": h["score"]}
            for h in hits]


@app.post("/api/paper")
def paper(body: PaperBody, _=Depends(require_token)):
    try:
        return kernel.pku_paper(body.ref, max_chars=body.max_chars)
    except Exception:  # Europe PMC unreachable
        raise HTTPException(status_code=502, detail="Paper lookup failed")


@app.get("/api/concerns")
def concerns(_=Depends(require_token)):
    return kernel.pku_concerns()
