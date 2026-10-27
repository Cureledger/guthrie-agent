# Guthrie HTTP service

A small FastAPI wrapper around the `guthrie` skill's retrieval brain
(`../kernel.py`). Same cite-or-refuse contract, same code path the eval scored.
Its one caller is the Phebe API, on behalf of signed-in Phebe members.

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

Railway builds `serve/Dockerfile` from the repo root; see [`../DEPLOY.md`](../DEPLOY.md).
The image bakes in `kernel.py`, the index and the MiniLM weights, so the
container is self-contained and starts offline.

## Endpoints

Every `/api/*` request needs `Authorization: Bearer $GUTHRIE_API_TOKEN`.

| method | path | body | returns |
|---|---|---|---|
| GET | `/health` | — | `{status, n_chunks, index_version, answer_model}` |
| POST | `/api/ask` | `{question}` | `{answer, citations, hits, refused, medical_flag}` |
| POST | `/api/search` | `{query, k?, source?}` | `[{citation, title, url, source, year, score}]` |

`/api/ask` always reads 8 passages and gives a brief answer, with the kernel's
own relevance floor. `source` filter for search: `literature` /
`guideline_fulltext` / `commons`.

## How Phebe calls it

The chat page is app.phebe.life/guthrie (phebe.life/guthrie forwards there).
The page sends the member's question to the Phebe API, which checks the session,
applies the member's own limit, and calls `/api/ask` server-side with the
secret. The member never sees this service's address. `refused` and
`medical_flag` let the page show the right note (rephrase, or talk to your
clinic); the page lists the sources, each linked to the paper on PubMed.
