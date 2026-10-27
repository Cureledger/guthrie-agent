# Guthrie — Corpus Manifest

*What Guthrie's brain knows, where it comes from, and how each claim is authorized.*

Guthrie is the PKU community agent (named for Robert Guthrie, who invented the
newborn-screening heel-prick test in 1963). In his "PKU genius" form he answers
from a **hybrid retrieval index** built from two layers, and he **cites or
refuses** — he never asserts a fact he cannot ground in a retrieved source.

This manifest is the *legal-review* object for the brain: it fixes exactly what
is in scope, the exact queries that define the literature slice, and the
citation authority each source maps to. Changing the corpus means changing this
file (with a version bump and a reviewer of record), the same discipline the
[PKU Commons peer-review model](https://github.com/Cureledger/pku-commons/blob/main/docs/PEER-REVIEW.md) applies to the food list.

---

## Layer 1 — The PKU literature ("brains of the researchers")

**Source:** NCBI PubMed / PMC via E-utilities (`esearch` → `efetch`). No API key
required; contact email attached when available.

**Retrieval universe (frozen query).** Everything Guthrie can cite from the
literature is drawn from this one query:

```
phenylketonuria OR phenylketonurias OR hyperphenylalaninemia OR "phenylalanine hydroxylase deficiency"
```

- **Live count at freeze:** **9,659** PubMed records (see
  [`build/corpus_manifest_counts.json`](build/corpus_manifest_counts.json) for the
  timestamped pull).
- **Why this is tractable, not "big data":** the *entire* PKU literature is
  ~9.7k records. It embeds into a single local index in minutes on CPU, for
  cents. There is no knowledge-graph pipeline, no cluster, and no streaming
  ingestion — that scale does not exist for this disease. The corpus is small
  enough that one person can rebuild it from scratch with one command, which is
  the whole point for sustainability.

**Coverage domains (sub-queries).** These are not separate corpora; they are the
domains the [eval set](eval/) must exercise, with their live counts at freeze:

| Domain | Records | Query intent |
|---|---:|---|
| Dietary management | 3,181 | diet, medical food, protein substitute, phe intake |
| Blood-phe monitoring | 1,024 | blood phenylalanine, dried blood spot, monitoring |
| BH4 / sapropterin | 933 | sapropterin, tetrahydrobiopterin, Kuvan, BH4 |
| Neurocognitive outcomes | 869 | cognition, executive function, IQ, white matter |
| Guidelines / consensus | 650 | guideline, consensus, recommendation, standard of care |
| Maternal PKU | 608 | maternal phenylketonuria |
| Gene / enzyme therapy | 320 | gene therapy, mRNA, AAV, enzyme substitution |
| Pegvaliase | 200 | pegvaliase, Palynziq, phenylalanine ammonia lyase |
| Large neutral amino acids | 100 | LNAA |

Exact query strings are frozen in
[`build/corpus_manifest_counts.json`](build/corpus_manifest_counts.json).

**Ingestion policy (corpus v0.3):**
- **The whole universe.** Metadata + abstract for every record the frozen query
  returns (title, abstract, year, journal, authors, MeSH, PMID, DOI). No record
  cap and no year floor. The 1980s and 1990s cohort studies (the Collaborative
  Study of Children Treated for PKU, the Maternal PKU Collaborative Study) still
  underpin current thresholds and are in scope. Records without an abstract are
  skipped by `fetch_corpus.py`; that is the only filter.
- **Full text for every open-access paper**, Layer 1 and Layer 1b alike, from
  Europe PMC (`build/fetch_fulltext.py`, no key). The body is indexed section
  by section, tables included, as `source: fulltext`, citing the same `[PMID]`
  as the abstract and carrying the same slice tag. Papers without an
  open-access copy stay as abstracts until one appears; each run rechecks new
  records and reports the split in `build/raw/fulltext_status.json`.
- **Licences are not filtered.** Every paper Europe PMC serves as XML is
  indexed, whatever its licence: CC BY, and also non-commercial and
  no-derivatives licences. The built index, which holds these texts in
  pieces, is a public release asset of this repository. Chosen on 2026-10-27
  to keep the v0.3 coverage.
- **PMC open-access full text** for the guidelines/consensus subset
  (`build/fetch_guidelines_fulltext.py`), kept as its own source so guideline
  text can be filtered for directly.
- **Pulling one paper on demand.** `pku_paper(ref)` in `kernel.py` fetches a
  single paper live from Europe PMC by PMID, PMC id or DOI: full text when it
  is open access, the abstract otherwise. This is how a session reads a paper
  that retrieval surfaced, or one outside the index, for discussion.

**Supplemental inclusions (outside the universe query).** A paper that is
in scope but never uses a universe term is listed, one PMID per line with a
reason, in `build/supplemental_pmids.txt` and fetched with
`fetch_corpus.py --pmids`. Each entry is a manifest change: it needs a reviewer
of record here.

| PMID | Why it is outside the query | Reviewer |
|---|---|---|
| 42561449 | Khan et al. 2026, *Biochem Cell Biol* — comprehensive PAH-pathway map (Guelph carrier series). Abstract says "PAH pathway", never "phenylketonuria". | Nina Kilbride, 2026-10-06 |

**Citation authority:** every literature chunk carries its **PMID** (and DOI/PMCID
when present). A literature claim Guthrie makes must cite `[PMID:xxxxxx]`.

---

## Layer 1b — The pterin (BH4) and monoamine-synthesis disorders (corpus v0.2)

**Why it is here.** PKU's downstream deficit, impaired serotonin and dopamine
synthesis, is the *primary* deficit in the tetrahydrobiopterin (BH4) disorders
and the monoamine-synthesis disorders. Those clinics have treated it for forty
years with precursors (5-HTP, L-DOPA, BH4), titrated against CSF metabolites and
prolactin, and their natural-history and dosing literature is the only place
that evidence exists. Guthrie holds it so he can answer "how is the same deficit
treated in the sister disorders" with citations, while never passing a pterin
finding off as a PKU finding.

**Source:** PubMed via E-utilities, same fetcher (`fetch_corpus.py --slice pterin`).

**Retrieval universe (frozen union of domain queries, minus Layer 1, 2000+).**
Every multi-word term is a quoted phrase PubMed indexes as a phrase; phrases it
would split into word-ANDs (e.g. "paediatric neurotransmitter disorders") were
tested and excluded. Exact strings are in `build/fetch_corpus.py::PTERIN_DOMAINS`
and `build/corpus_manifest_counts.json`.

| Domain | Total | Overlap w/ Layer 1 | In slice |
|---|---:|---:|---:|
| BH4 deficiencies (PTPS, DHPR, GTPCH, SR, PCD, DNAJC12) | 1,376 | 509 | 491 |
| Dopa-responsive dystonia / Segawa | 740 | 47 | 506 |
| Monoamine-synthesis disorders (AADC, TH, DBH) | 521 | 12 | 430 |
| Precursor therapy in these disorders (5-HTP, L-DOPA, carbidopa, BH4, sepiapterin) | 1,107 | 245 | 584 |
| 5-HTP clinical literature (depression, anxiety, sleep, trials) | 1,075 | 8 | 415 |
| BH4 and mental health (human) | 365 | 93 | 206 |
| Monoamine biomarkers (CSF HVA/5-HIAA, prolactin, pterins) | 375 | 115 | 142 |
| GCH1 vascular/pain reviews | 65 | 7 | 50 |
| **Union** | **4,149** | **629** | **2,048** |

**Ingestion:** all 2,048 slice records were fetched (no cap reached); 1,902 had
abstracts and are indexed. The 629 overlap PMIDs are not re-fetched; the 331 of
them inside the capped Layer 1 pull are tagged `pku,pterin`.

**Slice tagging and the cross-disease rule.** Every literature chunk carries
`slice` in its `extra` JSON (`pku`, `pterin`, or `pku,pterin`). The kernel labels
pterin passages `(literature/pterin, year)` in the context block, and the system
prompt rule (4) requires Guthrie to name the disease a pterin passage concerns
and never present it as a PKU result. Citation authority is unchanged: `[PMID:x]`.

**Not in scope (yet):** full-text guidelines for the BH4 disorders (the 2020
consensus guideline is in as an abstract, PMID 32456656); the iNTD registry,
which is center-access only.

---

## Layer 2 — The PKU Commons "market" ("knowledge of the market")

Guthrie also indexes the community's own infrastructure so he can answer
"which app is accurate?", "what does the food list say?", and "how is quality
guaranteed?" — routing to the real artifacts instead of improvising.

| Source doc | What it authorizes Guthrie to say |
|---|---|
| [`benchmark/BENCHMARK.md`](https://github.com/Cureledger/pku-commons/blob/main/benchmark/BENCHMARK.md) | the accuracy standard and how estimators are scored |
| [`benchmark/leaderboard.md`](https://github.com/Cureledger/pku-commons/blob/main/benchmark/leaderboard.md) | current measured estimator accuracy (the answer to "which is best") |
| [`docs/PEER-REVIEW.md`](https://github.com/Cureledger/pku-commons/blob/main/docs/PEER-REVIEW.md) | the two-layer (legal + scientific) governance model |
| [`docs/pain-points.md`](https://github.com/Cureledger/pku-commons/blob/main/docs/pain-points.md) | TruPKU / community pain points (what to build) |

| Cambrooke low-protein foods table (`phebe/phe-estimator/cambrooke_low_protein_foods.json`) | living-food-list product data, itself sourced to a dated Cambrooke nutrition table |

**Removed 2026-10-11:** the Phebe app spec, strategic thesis and scale
specifications. They are internal documents and were never meant to be
retrievable; the layer now holds only documents public in the pku-commons
repository.

**Citation authority:** market chunks cite `[Commons:<doc>]` (e.g.
`[Commons:leaderboard]`). Food/nutrition facts that trace to USDA FoodData
Central carry `[FDC:<id>]`; a clinician/RD sign-off is itself a citable
authority per the peer-review model.

---

## The contract (carried over from the ElizaOS Guthrie)

1. **Cite or refuse.** No fact without a retrieved source. If retrieval is weak,
   Guthrie says so and points to the blog / a clinician — he does not fabricate a
   PMID. (This is the *legal-review* standard applied to the brain.)
2. **No medical advice, diagnosis, or dosing** for an individual. Guthrie
   explains what the *literature* says and hands care decisions to clinicians.
3. **Market questions route to the benchmark**, not to opinion. "Which estimator
   is most accurate" is answered from the leaderboard, which is settled by
   measurement.
4. **No invented business/fundraising detail** (unchanged from the funnel agent).

---

## Reproducibility

- `build/fetch_corpus.py` — pulls Layer 1 from E-utilities into `build/raw/`.
- `build/build_index.py` — normalizes both layers into the hybrid index.
- One command rebuilds everything from source; `--since YYYY/MM/DD` does an
  incremental refresh so the corpus stays live without a dedicated maintainer.

## Refresh log

| Version | Date (UTC) | Change | Reviewer |
|---|---|---|---|
| v0 | 2026-08-07 | Initial freeze: 3,700 literature records (cap 4,000, with-abstract), 26 guideline sections, 74 market chunks. | Nina Kilbride |
| v0.1 | 2026-10-06 | Incremental `--since 2026/08/01` (45 matched, 4 already held, 38 appended) + 1 supplemental inclusion (PMID 42561449). Fetcher: `--since`/`--pmids` now merge into the existing file instead of overwriting; titles with inline markup no longer truncate. 3,739 literature records. | Nina Kilbride |
| v0.2 | 2026-10-06 | Layer 1b added: pterin (BH4) and monoamine-synthesis disorders, 2,048 records matched, 1,902 indexed, slice-tagged; kernel labels pterin passages and the prompt carries the cross-disease rule; skill triggers extended. Index 5,741 chunks. | Nina Kilbride |
| v0.3 | 2026-10-11 | Removed the 4,000 cap and 2010 floor (never in the plan; AI-introduced in v0 without disclosure): whole universe, no year floor. Full text for every open-access paper (Europe PMC) indexed as `source: fulltext`. Added `pku_paper()` for live single-paper pulls. Abstract-only papers stay as abstracts. | Nina Kilbride |
| v0.3 port | 2026-10-27 | Moved into Cureledger/guthrie-agent. The corpus accumulates run by run in CI (all 9,712 matching PMIDs attempted, 6,090 with an abstract) and every record was re-read so titles with inline markup are whole (`PARSE_VERSION` 2). Layer 1b, supplemental inclusions, full text and `pku_paper()` ported from v0.3: 6,091 PKU and 1,910 pterin records, 1,564 with full text, 53,364 chunks. The consumer topics and nutrition guidance from Nina's v0.4 were not ported. | pending |

**Version:** corpus v0.3 · **Reviewer of record:** Nina Kilbride · v0 frozen at the
timestamp in `build/corpus_manifest_counts.json`; refreshes are logged there and above.

