# Guthrie

DEPRECATED in favour of Cureledger/Cureledger2026 repo

**Patient-sovereign rare disease data agent**, powered by [ElizaOS](https://elizaos.ai).

Named after [Robert Guthrie](https://en.wikipedia.org/wiki/Robert_Guthrie) (1916–1995), the microbiologist who invented the newborn screening heel-prick test in 1963 — the technical accident of history that gave PKU patients a chance.

Guthrie is the community-facing AI agent for the Guthrie platform (a Cureledger Inc. project). It helps patients understand rare diseases, navigate the product ecosystem via [Zebra Reports](https://zebrareports.com), and learn how their data can contribute to cures.

## Quick start

```bash
# Install dependencies (requires bun)
bun install

# Copy and configure environment
cp .env.example .env
# Edit .env with at least one model provider key

# Development mode
bun run dev

# Production
bun run build
bun run start
```

## Docker

```bash
# Build and run with Postgres
docker compose up -d
```

## Knowledge domains

- **7,000+ rare diseases** affecting 30M Americans
- **Newborn screening** and the RUSP panel (PKU, galactosemia, MSUD, etc.)
- **Ehlers-Danlos Syndrome** — 13 subtypes, comorbidities, product recommendations
- **N-of-1 research** — dense longitudinal data as an engine of cures
- **FDA regulatory pathways** — Plausible Mechanism Framework, 21st Century Cures Act, ISTAND
- **Patient data sovereignty** — data trusts, conditional reidentification, HIPAA/GDPR

## Architecture

```
src/
  character.ts   # Guthrie's personality, knowledge, and communication style
  knowledge.ts   # Structured rare disease knowledge graph
  plugin.ts      # Custom actions (disorder lookup, product search, etc.)
  index.ts       # ElizaOS project entry point
```

## Legal

Guthrie is a product of **Cureledger Inc.** (Delaware C-Corp) — US Patent 12,095,919 B2.
