# Deploying the Guthrie research agent

The FastAPI service (`serve/serve.py`) answers PKU questions with cite-or-refuse
grounding over a hybrid BM25 + MiniLM index. It lives in this repo and is
deployed on **Railway** (Docker). Only Phebe members can ask: the chat page is
app.phebe.life/guthrie, the Phebe API checks the member's session and limits
each member, and then calls `/api/ask` with a shared secret
(`GUTHRIE_API_TOKEN`). No browser calls this service, so it has no CORS and no
Turnstile, and it refuses any request without the secret.

## The index is built in CI, not committed

The ~40MB index (`chunks.sqlite`, `embeddings.npy`, `bm25.pkl`) is git-ignored.
It is rebuilt from public sources (PubMed E-utilities — no API key) by
**`.github/workflows/build-index.yml`** and published as the **`index-latest`**
GitHub Release asset. The `Dockerfile` downloads that asset at build time.
The repo is public, so the download needs no token. The code being public
does not open the service: every question still needs `GUTHRIE_API_TOKEN`.

This keeps git clean, keeps deploys fast and reproducible, and lets the corpus
refresh on a schedule (weekly + on-demand) with no maintainer.

## First-time deploy (do these in order)

1. **Build the index once.** GitHub → Actions → *Build PKU index* → *Run
   workflow*. It fetches the corpus, builds the index, and creates the
   `index-latest` prerelease with `pku_index.tar.gz`. (Until this exists, the
   Docker build's download step fails by design.)

2. **Create the Railway service** from this repo:
   - Root Directory: empty (the repo root). Railway finds `Dockerfile` there
     and builds it; nothing else selects the builder. New Railway services
     ignore `railway.toml`, so the repo has none.
   - Settings → Deploy: Healthcheck Path `/health`, Healthcheck Timeout
     `300` (the first start loads the index and the MiniLM weights), Restart
     Policy "On failure".
   - Variable: `ANTHROPIC_API_KEY` = a funded key on a workspace with model
     access. (A key authenticates to its owning workspace — check the
     `anthropic-workspace-id` response header if calls 401/403.)
   - Variable: `GUTHRIE_API_TOKEN` = a long random secret. The Phebe API
     holds the same value (Worker secret `GUTHRIE_API_TOKEN`); set both at once.

3. **Deploy.** Railway builds the image (pulling `index-latest`), starts
   uvicorn on `$PORT`, and health-checks `GET /health`.

4. **Verify:** `GET https://<service>.up.railway.app/health` →
   `{status, n_chunks, index_version, answer_model}`. `POST /api/ask` without
   the secret must return 401; with `Authorization: Bearer <secret>` it
   answers.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (required) | Grounding LLM |
| `GUTHRIE_ANSWER_MODEL` | `claude-haiku-4-5-20251001` | Answer model (use a **live** id; dated snapshots get retired → 404) |
| `GUTHRIE_API_TOKEN` | — (required) | `/api/*` requires `Authorization: Bearer <token>`. Unset = every `/api/*` request is refused (503). The Phebe API sends it |
| `GUTHRIE_RATE_LIMIT_PER_MIN` | `60` | Answers per minute across all members, counted only after the secret checks out. A backstop if the secret leaks; each member's own limit is in the Phebe API |

## Growing / refreshing the corpus

The corpus **accumulates** across runs — it does not re-snapshot the most-recent
N. Each *Build PKU index* run:

1. downloads the corpus grown so far (`literature.jsonl.gz` + `fetched_ids.txt`
   from the `index-latest` release),
2. fetches up to **`max_records`** *new* PubMed records not yet attempted
   (deduped by PMID; `fetched_ids.txt` tracks every attempted id so abstract-less
   records don't stall progress),
3. rebuilds the index and republishes both the index and the grown corpus.

So to **grow it in chunks**, just re-run the workflow — each run adds another
`max_records` and prints `remaining` until the universe (~9.7k records) is
covered. Set **`max_records = 0`** to fetch everything remaining in one run. The
weekly schedule keeps adding/refreshing on its own. After any run, redeploy on
Railway so the image pulls the new `index-latest` asset.
