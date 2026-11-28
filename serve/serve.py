#!/usr/bin/env python3
"""Guthrie as a standalone HTTP service.

Wraps the guthrie skill's retrieval brain (kernel.py) behind a small FastAPI app.
Two kinds of caller:

  * The Phebe API, on behalf of a signed-in Phebe member (the chat page is
    app.phebe.life/guthrie). It calls /api/ask with a shared secret. That route
    calls kernel.pku_ask itself (not a copy) and only injects the grounding LLM
    via the Anthropic API (the skill's host.llm is not present outside Claude
    Science), so the refusal gate, medical flag, and citation logic are
    literally the same code the eval scored. Every answer is a paid call, so
    this route stays behind the token.

  * Any other agent. Other agents have their own language model; what they
    need from Guthrie is his retrieval: the ranked passages with PMIDs, one
    paper's full text, and the corpus slices. Those make no model call and are
    served to everyone, rate-limited, over plain HTTP (/api/search, /api/paper,
    /api/concerns, with the OpenAPI spec at /openapi.json) and over the Model
    Context Protocol (/mcp, streamable HTTP, no auth). /llms.txt describes the
    service for crawlers.

    ANTHROPIC_API_KEY=sk-...  GUTHRIE_API_TOKEN=...  GUTHRIE_INDEX_DIR=./pku_index  uvicorn serve:app

Endpoints:
    GET  /              -> what this is, with links
    GET  /llms.txt      -> the same, for crawlers
    GET  /health        -> {status, n_chunks, index_version, answer_model, answers}
    GET  /openapi.json  -> the spec of the routes below (/docs renders it)
    POST /api/ask       {question}               -> {answer, citations, hits, refused, medical_flag}   [token]
    POST /api/search    {query, k?, source?, slices?} -> [{citation, title, score, url, ...}]          [public]
    POST /api/paper     {ref, max_chars?}        -> one paper: full text if open access, else abstract  [public]
    GET  /api/concerns  -> [{key, label, papers}] the literature slices (PKU, pterin)                   [public]
    *    /mcp           -> MCP server: tools pku_search, pku_paper, pku_concerns, guthrie_index_info   [public]

The answer writer is chosen by environment:
    ANTHROPIC_API_KEY set     -> Anthropic API (GUTHRIE_ANSWER_MODEL); production
    GUTHRIE_OLLAMA_MODEL set  -> a local model through Ollama (GUTHRIE_OLLAMA_URL)
    GUTHRIE_ANSWERS=extractive -> no model: one lead sentence per source, cited
    none of these             -> answer=null with the ranked sources

The answer contract is identical to the skill: cite-or-refuse, medical-advice
flag + clinician deferral, off-topic refusal. This is the same code path the
eval scored, so the number on the website is the number in eval/report.md.
"""
import contextlib
import hmac
import os
import sys
import time
from collections import deque

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from starlette.routing import Route

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
# with this shared secret. A request to /api/ask without the secret is
# refused, and with no secret configured /api/ask refuses every request (fail
# closed). The retrieval routes do not use the secret: they make no model call.
API_TOKEN = os.environ.get("GUTHRIE_API_TOKEN", "").strip()
if not API_TOKEN:
    print("[auth] GUTHRIE_API_TOKEN is not set: /api/ask refuses every request", flush=True)

# A ceiling on answers per minute across all members, in case the secret ever
# leaks. Members' own limits live in the Phebe API. One Railway replica runs
# this process, so an in-memory counter is effective. Counted after the secret
# is checked, so strangers cannot use up the members' allowance.
RATE_LIMIT_MAX = int(os.environ.get("GUTHRIE_RATE_LIMIT_PER_MIN", "60"))
RATE_LIMIT_WINDOW = 60.0
_rl_hits: deque = deque()

# The retrieval routes are open to any agent. Their own counter, separate from
# the members' answer allowance, so a crawler cannot starve the Phebe chat.
# Retrieval is a CPU-bound in-memory search (a few ms); /api/paper also makes
# one call to Europe PMC.
PUBLIC_RATE_LIMIT_MAX = int(os.environ.get("GUTHRIE_PUBLIC_RATE_LIMIT_PER_MIN", "240"))
_public_hits: deque = deque()

SERVICE_URL = os.environ.get("GUTHRIE_PUBLIC_URL", "https://guthrie-agent-production.up.railway.app").rstrip("/")
REPO_URL = "https://github.com/Cureledger/guthrie-agent"

DESCRIPTION = """Guthrie is the PKU (phenylketonuria) research agent built by Phebe and the PKU Commons.
He holds the open PKU literature: every PubMed record on PKU and the BH4/pterin disorders,
the open-access full texts, the guideline full texts, and the PKU Commons documents, in a
hybrid BM25 + MiniLM index that rebuilds from public sources every week.

The retrieval routes are open to any agent, no key: ranked passages with PMIDs
(`POST /api/search`), one paper's full text or abstract (`POST /api/paper`), and the
corpus slices (`GET /api/concerns`). The same three are MCP tools at `/mcp`
(streamable HTTP). Cite what you retrieve by PMID; Guthrie does not give medical advice,
diagnosis, or dosing for an individual, and neither should an answer built on him.

`POST /api/ask` writes a grounded, cited answer with a language model. It costs money per
call, so it is reserved for Phebe members through the Phebe API and needs a bearer token."""

# The MCP server (streamable HTTP, stateless, JSON responses) is mounted on the
# same process at /mcp. Its tools call the kernel directly, like the routes.
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

mcp = MCPServer(
    "guthrie",
    title="Guthrie, the PKU research agent",
    version="1",
    website_url="https://phebe.life",
    instructions=(
        "Guthrie: retrieval over the open PKU (phenylketonuria) literature. Use pku_search "
        "to find passages (each carries a PMID citation and PubMed url), pku_paper to read "
        "one paper, pku_concerns to list the corpus slices. Cite every claim you build on a "
        "hit by its PMID. Do not give medical advice, diagnosis, or dosing for an individual; "
        "those are decisions for a metabolic clinician."
    ),
)
# Public service behind Railway's proxy: the Host header is the public hostname,
# so the SDK's localhost-only DNS-rebinding guard must be off.
mcp_app = mcp.streamable_http_app(
    streamable_http_path="/mcp", json_response=True, stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Guthrie - PKU research agent",
    version="1",
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "retrieval", "description": "Open to any agent. No key. Rate-limited per minute across all callers."},
        {"name": "answer", "description": "Phebe members only, through the Phebe API. Bearer token."},
        {"name": "service", "description": "What this is and whether it is up."},
    ],
)
# Browser-based agents (and the /docs page) may call the open routes.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
# A Route, not a Mount: a Mount at /mcp answers the bare path with a 307 to
# /mcp/, which MCP clients do not follow for POST.
app.router.routes.append(Route("/mcp", mcp_app))


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


def public_rate_limit():
    now = time.monotonic()
    while _public_hits and now - _public_hits[0] > RATE_LIMIT_WINDOW:
        _public_hits.popleft()
    if len(_public_hits) >= PUBLIC_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    _public_hits.append(now)


# A question is the question and nothing else: how many passages to read, the
# answer length and the relevance floor are the server's choice, so no caller
# can make a call cost more or skip the off-topic refusal.
ASK_K = 8
ASK_MODE = "brief"


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="A question or topic in plain words.")
    k: int = Field(default=8, ge=1, le=20, description="How many passages to return.")
    source: str | None = Field(default=None, max_length=64,
                               description="Restrict to one layer: literature (abstracts), fulltext (open-access paper sections), guideline_fulltext, or commons (PKU Commons documents).")
    slices: list[str] | None = Field(default=None, max_length=8,
                                     description="Restrict to corpus slices from /api/concerns, e.g. ['pku'] or ['pterin'].")


class PaperBody(BaseModel):
    ref: str = Field(min_length=1, max_length=200, description="A PMID ('12345678' or 'PMID:12345678'), a PMC id ('PMC1234567'), or a DOI.")
    max_chars: int = Field(default=60000, ge=0, le=400000, description="Truncate the body to this many characters; 0 = no limit.")


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


def _search(query, k=8, source=None, slices=None):
    hits = kernel.pku_search(query, k=k, source=source, slices=slices)
    return [{"citation": h["citation"], "title": h["title"], "url": h["url"],
             "source": h["source"], "year": h["year"], "score": h["score"]}
            for h in hits]


def _paper(ref, max_chars=60000):
    try:
        return kernel.pku_paper(ref, max_chars=max_chars)
    except Exception:  # Europe PMC unreachable
        raise HTTPException(status_code=502, detail="Paper lookup failed")


LLMS_TXT = f"""# Guthrie, the PKU research agent

> {DESCRIPTION.splitlines()[0]}

## Use Guthrie from an agent

- OpenAPI spec: {SERVICE_URL}/openapi.json (search, paper, concerns are open; no key)
- MCP server (streamable HTTP, no auth): {SERVICE_URL}/mcp
- Claude Code plugin: `claude plugin marketplace add Cureledger/guthrie-agent` then `claude plugin install guthrie@guthrie-agent`
- Source, corpus manifest, eval: {REPO_URL}

## Rules of use

- Every passage carries a PMID and a PubMed url. Cite it.
- Guthrie reports what the literature says. He does not diagnose, recommend a treatment, or set a dose or diet for an individual.
- The corpus is PKU and the BH4/pterin disorders. Off-topic questions find nothing.

## Who built it

- Phebe, the PKU precision nutrition app and research co-op: https://phebe.life
- PKU Commons, open infrastructure for PKU apps: https://github.com/Cureledger/pku-commons
- Cureledger, Inc.: https://cureledger.com/llms.txt
"""


@app.get("/", tags=["service"], summary="What this service is")
def root():
    return {"name": "Guthrie, the PKU research agent",
            "description": DESCRIPTION.splitlines()[0],
            "openapi": f"{SERVICE_URL}/openapi.json", "docs": f"{SERVICE_URL}/docs",
            "mcp": f"{SERVICE_URL}/mcp", "llms_txt": f"{SERVICE_URL}/llms.txt",
            "repository": REPO_URL, "built_by": {"phebe": "https://phebe.life",
                                                 "pku_commons": "https://github.com/Cureledger/pku-commons",
                                                 "cureledger": "https://cureledger.com"}}


@app.get("/llms.txt", tags=["service"], summary="This service, for crawlers", response_class=PlainTextResponse)
def llms_txt():
    return LLMS_TXT


@app.get("/health", tags=["service"], summary="Is the index loaded")
def health():
    info = kernel.guthrie_index_info()
    return {"status": "ok", "n_chunks": info["n_chunks"],
            "index_version": info["version"], "answer_model": ANSWER_MODEL,
            "answers": _answers()}


@app.post("/api/ask", tags=["answer"], summary="A grounded, cited answer (Phebe members, bearer token)")
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


@app.post("/api/search", tags=["retrieval"], summary="Ranked passages from the PKU literature, each with a PMID")
def search(body: SearchBody, _=Depends(public_rate_limit)):
    """Hybrid BM25 + dense retrieval over the whole corpus. `citation` is the
    label to cite (`[PMID:...]` or `[Commons:...]`), `url` the PubMed or source page,
    `score` the fused rank score. Follow a hit with /api/paper to read the paper."""
    return _search(body.query, k=body.k, source=body.source, slices=body.slices)


@app.post("/api/paper", tags=["retrieval"], summary="One paper: full text if open access, else the abstract")
def paper(body: PaperBody, _=Depends(public_rate_limit)):
    """Live lookup on Europe PMC (no key). Returns {pmid, pmcid, doi, title, year,
    journal, abstract, sections, full_text, url, citation}. `sections` is
    [{heading, text}]; `full_text` is false when only the abstract is open."""
    return _paper(body.ref, max_chars=body.max_chars)


@app.get("/api/concerns", tags=["retrieval"], summary="The corpus slices and their paper counts")
def concerns(_=Depends(public_rate_limit)):
    return kernel.pku_concerns()


# ---- MCP tools: the same retrieval, for agents that speak MCP ----------------

@mcp.tool()
def pku_search(query: str, k: int = 8, source: str | None = None, slices: list[str] | None = None) -> list[dict]:
    """Search the open PKU (phenylketonuria) literature. Returns up to k passages
    ranked by hybrid BM25 + dense score. Each hit has `citation` (a [PMID:...] or
    [Commons:...] label to cite), `title`, `url` (PubMed or source page), `source`
    layer, `year`, and `score`. `source` restricts to one layer: literature
    (abstracts), fulltext (open-access paper sections), guideline_fulltext, or
    commons (PKU Commons documents). `slices` restricts to corpus slices from
    pku_concerns, e.g. ["pku"] or ["pterin"]. Cite every claim you build on a hit."""
    k = max(1, min(int(k), 20))
    public_rate_limit()
    return _search(query, k=k, source=source, slices=slices)


@mcp.tool()
def pku_paper(ref: str, max_chars: int = 60000) -> dict:
    """Read one paper: the full text when it is open access, otherwise the
    abstract. `ref` is a PMID ("12345678" or "PMID:12345678"), a PMC id
    ("PMC1234567"), or a DOI. Returns {pmid, pmcid, doi, title, year, journal,
    abstract, sections: [{heading, text}], full_text (bool), url, citation}.
    Live lookup on Europe PMC; max_chars truncates long bodies (0 = no limit)."""
    public_rate_limit()
    return _paper(ref, max_chars=max(0, min(int(max_chars), 400000)))


@mcp.tool()
def pku_concerns() -> list[dict]:
    """The corpus slices Guthrie holds, with paper counts: [{key, label, papers}].
    Keys are what pku_search accepts in `slices` (e.g. pku, pterin)."""
    public_rate_limit()
    return kernel.pku_concerns()


@mcp.tool()
def guthrie_index_info() -> dict:
    """Build metadata for the index Guthrie is answering from: version,
    embedding model, chunk counts by source layer and slice, build time (UTC)."""
    return kernel.guthrie_index_info()
