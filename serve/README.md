# Guthrie HTTP service

A small FastAPI wrapper around the `guthrie` skill's retrieval brain
(`../kernel.py`). Same cite-or-refuse contract, same code path the eval scored.
Two kinds of caller: the Phebe API, on behalf of signed-in Phebe members, which
asks for written answers; and any other agent, which gets the retrieval (ranked
passages with PMIDs, papers, corpus slices) over plain HTTP or MCP, no key.

## Run locally

```bash
python -m venv .venv && ./.venv/bin/pip install -r serve/requirements.txt
export ANTHROPIC_API_KEY=sk-...
export GUTHRIE_API_TOKEN=dev-secret             # any value; callers send it
export GUTHRIE_INDEX_DIR=$PWD/pku_index         # or unpack pku_index_v0.tar.gz here
./.venv/bin/uvicorn serve:app --app-dir serve --port 8000

curl localhost:8000/health
curl -s localhost:8000/api/ask -H 'content-type: application/json' \
  -H 'authorization: Bearer dev-secret' \
  -d '{"question":"How does pegvaliase lower blood phe?"}' | jq .answer
```

## Deploy

Railway builds the `Dockerfile` at the repo root; see [`../DEPLOY.md`](../DEPLOY.md).
The image bakes in `kernel.py`, the index and the MiniLM weights, so the
container is self-contained and starts offline.

## Endpoints

| method | path | auth | body | returns |
|---|---|---|---|---|
| GET | `/` | open | — | what this is, with links |
| GET | `/llms.txt` | open | — | the same, for crawlers |
| GET | `/health` | open | — | `{status, n_chunks, index_version, answer_model, answers}` |
| GET | `/openapi.json` | open | — | the spec; `/docs` renders it |
| POST | `/api/ask` | `Authorization: Bearer $GUTHRIE_API_TOKEN` | `{question}` | `{answer, citations, hits, refused, medical_flag}` |
| POST | `/api/search` | open | `{query, k?, source?, slices?}` | `[{citation, title, url, source, year, score}]` |
| POST | `/api/paper` | open | `{ref, max_chars?}` | one paper: `{pmid, pmcid, doi, title, year, journal, abstract, sections, full_text, url, citation}` |
| GET | `/api/concerns` | open | — | `[{key, label, papers}]` |
| POST | `/mcp` | open | MCP streamable HTTP | tools `pku_search`, `pku_paper`, `pku_concerns`, `guthrie_index_info` |

`/api/ask` always reads 8 passages and gives a brief answer, with the kernel's
own relevance floor. It is the only route that calls a language model, so it is
the only one behind the token. `source` filter for search: `literature` /
`fulltext` / `guideline_fulltext` / `commons`; `slices` takes keys from
`/api/concerns` (`pku`, `pterin`).

The open routes share one rate limit (`GUTHRIE_PUBLIC_RATE_LIMIT_PER_MIN`,
default 240 a minute across all callers), separate from the members' answer
allowance, so a crawler cannot starve the Phebe chat.

## MCP

The same retrieval is an MCP server on the same process, streamable HTTP,
stateless, JSON responses, no auth, at `/mcp`. Add it to any MCP client as a
remote server. The tool descriptions carry the contract (cite by PMID, no
medical advice). `../server.json` is the listing for the MCP registry and
`../plugins/guthrie/` the Claude Code plugin that installs it.

```bash
curl -s localhost:8000/mcp -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"pku_search","arguments":{"query":"sapropterin responsiveness","k":3}}}'
```

## How Phebe calls it

The chat page is app.phebe.life/guthrie (phebe.life/guthrie forwards there).
The page sends the member's question to the Phebe API, which checks the session,
applies the member's own limit, and calls `/api/ask` server-side with the
secret. The member never sees this service's address. `refused` and
`medical_flag` let the page show the right note (rephrase, or talk to your
clinic); the page lists the sources, each linked to the paper on PubMed.
