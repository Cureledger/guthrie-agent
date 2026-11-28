# Deploying the Guthrie research agent

The FastAPI service (`serve/serve.py`) answers PKU questions with cite-or-refuse
grounding over a hybrid BM25 + MiniLM index. It lives in this repo and is
deployed on **Railway** (Docker) at `https://guthrie-agent-production.up.railway.app`.

Two kinds of caller. Only Phebe members can ask for a written answer: the chat
page is app.phebe.life/guthrie, the Phebe API checks the member's session and
limits each member, and then calls `/api/ask` with a shared secret
(`GUTHRIE_API_TOKEN`). The retrieval routes (`/api/search`, `/api/paper`,
`/api/concerns`) and the MCP server at `/mcp` make no model call and are open
to any agent, no key, under their own rate limit. The OpenAPI spec is at
`/openapi.json` and `/llms.txt` describes the service for crawlers.

## The index is built in CI, not committed

The index (`chunks.sqlite`, `embeddings.npy`, `bm25.pkl`; 269 MB, 117 MB
packed) is git-ignored.
It is rebuilt from public sources (PubMed E-utilities and Europe PMC — no
API key) by
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
   uvicorn on `$PORT`, and health-checks `GET /health`. The service holds the
   whole index in memory: about 1.5 GB resident with full text.

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
| `GUTHRIE_PUBLIC_RATE_LIMIT_PER_MIN` | `240` | Retrieval requests per minute across all open callers (HTTP and MCP together). Separate counter from the members' answers |
| `GUTHRIE_PUBLIC_URL` | `https://guthrie-agent-production.up.railway.app` | The public origin, printed in `/`, `/llms.txt` and the spec |

## Being found by other agents

The service is only useful to other agents if they can find it. After a deploy
that carries the open routes and `/mcp`:

1. **MCP registry.** `server.json` at the repo root is the listing
   (`io.github.Cureledger/guthrie`, remote `streamable-http`). Publish it with
   the registry's `mcp-publisher` CLI (binaries on the
   [registry releases page](https://github.com/modelcontextprotocol/registry/releases),
   or Homebrew), from the repo root:
   `mcp-publisher login github` (a GitHub account in the Cureledger
   organization; the `io.github.<org>` namespace is verified against GitHub),
   `mcp-publisher validate`, then `mcp-publisher publish`. Bump `version` in
   `server.json` on each republish.
2. **Claude Code plugin.** `.claude-plugin/marketplace.json` makes this repo a
   marketplace and `plugins/guthrie/` the plugin (skill + `.mcp.json` pointing
   at `/mcp`). Nothing to publish: users run
   `claude plugin marketplace add Cureledger/guthrie-agent` then
   `claude plugin install guthrie@guthrie-agent`. Check with
   `claude plugin validate ./plugins/guthrie` before tagging.
3. **GitHub.** Give the repo topics (`phenylketonuria`, `pku`, `rare-disease`,
   `mcp`, `mcp-server`, `claude-skill`, `pubmed`, `retrieval`), a homepage
   (`https://phebe.life`) and a license file; an unlicensed repo is one most
   assistants will not recommend.
4. **The sites.** `phebe.life/llms.txt` and `cureledger.com/llms.txt` should
   link `/mcp` and the repo; `pku-commons.org` has no `llms.txt` yet.

## Growing / refreshing the corpus

The corpus **accumulates** across runs — it does not re-snapshot the most-recent
N. Each *Build PKU index* run:

1. downloads the corpus grown so far (the literature, pterin and full-text
   files with their id logs, from the `index-latest` release),
2. fetches up to **`max_records`** *new* PubMed records not yet attempted
   (deduped by PMID; `fetched_ids.txt` tracks every attempted id so abstract-less
   records don't stall progress),
3. rebuilds the index and republishes both the index and the grown corpus.

Full text works the same way. `build/fetch_fulltext.py` asks Europe PMC
about every paper not yet checked and keeps the open-access ones;
`fulltext_ids.txt` records what was checked, `fulltext_failed.txt` the papers
with no XML (rechecked with `--retry-failed`). The first run checks all
~8,000 papers, about an hour; later runs check only new ones. A batch that
Europe PMC refuses (HTTP 503) is not marked checked, so the next run takes it.

So to **grow it in chunks**, just re-run the workflow — each run adds another
`max_records` and prints `remaining` until the universe (~9.7k records) is
covered. Set **`max_records = 0`** to fetch everything remaining in one run. The
weekly schedule keeps adding/refreshing on its own. After any run, rebuild on
Railway so the image pulls the new `index-latest` asset:
`railway redeploy --from-source --service guthrie-agent`. A plain redeploy
reuses the image already built, with the old index.

When `build/fetch_corpus.py` changes how it reads a paper, bump its
`PARSE_VERSION`: the next run reads every older record again, so the fix
reaches the whole corpus and not only papers added afterwards.
