# Guthrie — the PKU research agent

*Phebe's PKU research agent; Phebe members ask him at app.phebe.life/guthrie.
Named for Robert Guthrie (1916–1995), who invented the newborn-screening
heel-prick test in 1963.*

Guthrie answers PKU questions grounded in the peer-reviewed literature and the
PKU Commons infrastructure, with an inline citation on every claim. He is a
Claude Skill: a portable retrieval brain plus a persona contract. He **cites or
refuses** — he never asserts a fact he cannot ground in a retrieved source, and
he does not give medical advice, diagnosis, or dosing for an individual.

## Why this exists

PKU apps and PKU information sources tend to die when a solo developer moves on,
and there has been no standard for judging whether an AI answer about PKU is
trustworthy. Guthrie is built so that a reliable, *checkable* PKU knowledge
agent exists and stays reliable even without a dedicated maintainer:

- the corpus rebuilds from public sources with one command (no API key);
- every answer carries a citation a clinician or researcher can verify;
- Guthrie's own accuracy is peer-reviewed by a reproducible eval, not asserted.

This is the same two-layer quality model the rest of PKU Commons uses
([legal-style review of the knowledge, scientific-style review of the
outputs](https://github.com/Cureledger/pku-commons/blob/main/docs/PEER-REVIEW.md)) — turned on the agent itself.

## What's here

| Path | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | the skill: persona, contract, `pku_ask`/`pku_search` API |
| [`kernel.py`](kernel.py) | the retrieval brain (hybrid BM25 + dense, cite-or-refuse) |
| [`CORPUS.md`](CORPUS.md) | the corpus manifest — exactly what Guthrie knows and on whose authority |
| [`build/`](build/) | reproducible fetch + index scripts (one command rebuilds) |
| [`eval/`](eval/) | the retrieval eval set + scored report (the scientific-review layer) |
| [`MIGRATION.md`](MIGRATION.md) | how this supersedes the ElizaOS Guthrie |
| [`serve/`](serve/) | the HTTP service Phebe calls; deploy notes in [`DEPLOY.md`](DEPLOY.md) |
| `pku_index/` | the built index (or unpack `pku_index_v0.tar.gz` here) |

## Quick start

```bash
# 1. environment
python -m venv .venv && ./.venv/bin/pip install rank_bm25 sentence-transformers numpy

# 2. build the brain from source (about an hour the first time, no API key)
python build/fetch_corpus.py                 # PubMed abstracts + metadata
python build/fetch_corpus.py --slice pterin  # Layer 1b: BH4 and monoamine disorders
python build/fetch_corpus.py --pmids build/supplemental_pmids.txt
python build/fetch_fulltext.py               # Europe PMC full text, every open-access paper
python build/fetch_guidelines_fulltext.py    # PMC open-access guideline full text
python build/build_market_layer.py           # public PKU Commons docs
python build/build_index.py                  # BM25 + MiniLM hybrid index -> pku_index/

# 3. use it (in a Claude Science session, the skill loads kernel.py for you)
python -c "import kernel; print(kernel.pku_ask('How does pegvaliase lower blood phe?')['answer'])"
```

## The numbers

- **Corpus (27 Oct 2026):** 6,091 PKU papers and 1,910 on the pterin (BH4) and
  monoamine-synthesis disorders, every one with its abstract; the full text of
  the 1,564 that have an open-access copy, section by section; 18 guideline
  full-text sections; 27 PKU Commons chunks. **53,364 indexed chunks**, 269 MB
  on disk (117 MB packed), built in about 7 minutes on a laptop CPU.
- **Memory:** the service holds the whole index in memory, about 1.5 GB
  resident (the abstracts-only index used about 650 MB).
- **Eval:** 85% citation recall (conservative), **100% groundedness — zero
  fabricated citations**, 100% correct medical + out-of-scope refusal on the
  v0 index with a model. See [`eval/report.md`](eval/report.md), and
  [`eval/EVAL.md`](eval/EVAL.md) for the retrieval-only check of this index.

## Staying live without a maintainer

```bash
# refresh: fetch papers not yet attempted, check them for full text, rebuild
python build/fetch_corpus.py && python build/fetch_corpus.py --slice pterin
python build/fetch_fulltext.py && python build/build_index.py
python eval/run_eval.py   # confirm the score held (regression gate)
```

The *Build PKU index* workflow runs this every Monday: it adds new papers,
checks them for full text and rebuilds the index. Anyone in the community can
run the same commands.
