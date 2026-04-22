# Deploy Guthrie (Eliza) to Railway

This service is the **long-running** ElizaOS API. The **Guthrie site** (Vercel) calls it via `ELIZAOS_API_URL`.

## 1. Create the Railway service

1. [Railway](https://railway.com) → **New project** → **GitHub** → select this repository.
2. **Settings** → **Root directory** → set to `guthrie` (if the whole monorepo is in one repo).
3. **Build:** Railway should pick up `guthrie/railway.toml` and `guthrie/Dockerfile`.
4. **Generate domain** (e.g. `guthrie-production.up.railway.app`) and copy the **HTTPS** URL. You will paste that into Vercel as `ELIZAOS_API_URL`.

## 2. Add Postgres (required for `@elizaos/plugin-sql`)

1. In the same Railway project → **New** → **Database** → **Add PostgreSQL**.
2. In the **Guthrie** service → **Variables**:
   - Add **`POSTGRES_URL`** and paste the **connection string** from the Postgres service (or use Railway’s *Variable Reference* to the Postgres `DATABASE_URL` / `POSTGRES_URL`).

## 3. Set secrets

In the Guthrie service **Variables**, add at least one LLM key (match what you use locally), for example:

- `OPENAI_API_KEY` (or the provider you configured in the Eliza project)

Add any other keys you use in production (see `.env.example`).

Railway sets **`PORT`** at runtime. `docker-entrypoint.sh` maps it to **`SERVER_PORT`** for the Eliza server. Do **not** set `PORT` yourself unless you know what you’re doing.

## 4. Point the marketing site (Vercel) at this API

In the **guthrie-site** Vercel project → **Settings** → **Environment variables** (Production):

| Name | Value |
|------|--------|
| `ELIZAOS_API_URL` | `https://&lt;your-railway-domain&gt;` (no trailing slash) |

Redeploy the Guthrie site. The Next.js route `app/api/chat` proxies to `$ELIZAOS_API_URL/api/...`.

## 5. Verify

- Open `https://&lt;railway-domain&gt;/api/agents` (or the route your build exposes) — you should get JSON, not 502.
- In the Guthrie UI, **Ask Guthrie** should return answers, not *“Guthrie agent not found / agent service not running”*.

## 6. What we need from you (manual steps)

Railway and Vercel do not read this repo for auth:

1. **GitHub** connected to Railway with access to this repo.
2. **A Railway public URL** you paste into Vercel as `ELIZAOS_API_URL`.
3. **Postgres** and **`POSTGRES_URL`** (or equivalent) on the Guthrie service.
4. **LLM / API keys** the agent needs, set only in Railway Variables (and never committed).

If deploy fails, check Railway **Build logs** and **Deploy logs**; common issues: missing `POSTGRES_URL`, missing API key, or the service not listening on the port Railway expects (this repo’s `docker-entrypoint.sh` addresses the port mapping).
