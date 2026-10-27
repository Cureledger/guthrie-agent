#!/usr/bin/env python3
"""Guthrie — build the hybrid retrieval index.

Reads the raw corpus (build/raw/*.jsonl), normalizes every document into
provenance-carrying chunks, and builds a portable hybrid index:

  * dense:  sentence-transformers all-MiniLM-L6-v2 embeddings (CPU, no API key)
  * lexical: BM25 (rank_bm25) over tokenized chunk text

Persisted to guthrie/pku_index/ :
  chunks.sqlite   — one row per chunk (text + full provenance + citation id)
  embeddings.npy  — float32 [n_chunks, 384], row order == sqlite rowid-1
  bm25.pkl        — tokenized corpus for BM25
  meta.json       — build stats, model name, version

One command rebuilds from source. Everything downstream (kernel.py) only reads
this directory, so the brain is fully reproducible from the fetch scripts.
"""
import os
# Force plain-HTTPS weight downloads. HuggingFace's newer Xet transfer client
# uses a protocol that is not reachable from the sandbox; plain HTTPS is.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_XET_DISABLE", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

import json, pickle, re, sqlite3, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.abspath(os.path.join(HERE, "..", "pku_index"))
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_word = re.compile(r"[a-z0-9]+")
def tokenize(text):
    return _word.findall(text.lower())

def literature_chunks(path, slice_name="pku", both=frozenset()):
    """One chunk per abstract (abstracts are already ~paragraph sized).

    slice_name tags which frozen universe the record came from ("pku" = Layer 1,
    "pterin" = Layer 1b). A PKU record whose PMID is also matched by the pterin
    query is tagged "pku,pterin" so the kernel can label cross-disease passages.
    """
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        text = f"{r['title']}\n\n{r['abstract']}"
        sl = slice_name
        if slice_name == "pku" and r["pmid"] in both:
            sl = "pku,pterin"
        yield {
            "source": "literature",
            "citation_id": f"PMID:{r['pmid']}",
            "cite_label": f"PMID:{r['pmid']}",
            "title": r["title"],
            "text": text,
            "year": str(r.get("year") or "")[:4],
            "journal": r.get("journal") or "",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/",
            "extra": json.dumps({"doi": r.get("doi"), "pmcid": r.get("pmcid"),
                                 "pub_types": r.get("pub_types", [])[:4],
                                 "slice": sl}),
        }

def guideline_chunks(path):
    """Section-level chunks from PMC full-text guidelines."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        for sec in r["sections"]:
            body = sec["text"]
            if len(body) < 200:
                continue
            head = sec.get("heading") or ""
            yield {
                "source": "guideline_fulltext",
                "citation_id": f"PMID:{r['pmid']}",
                "cite_label": f"PMID:{r['pmid']}",
                "title": f"{r['title']} — {head}" if head else r["title"],
                "text": (f"{head}\n\n{body}" if head else body),
                "year": "",
                "journal": "",
                "url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{r['pmcid']}/",
                "extra": json.dumps({"pmcid": r["pmcid"], "heading": head}),
            }

def _split(text, limit=1800):
    """Split a long section on paragraph, then sentence, boundaries into <= limit pieces."""
    if len(text) <= limit:
        return [text]
    out, buf = [], ""
    for para in text.split("\n"):
        if len(para) > limit:  # one giant paragraph: break on sentences
            for sent in re.split(r"(?<=[.!?])\s+", para):
                if len(buf) + len(sent) + 1 > limit and buf:
                    out.append(buf); buf = ""
                buf = (buf + " " + sent).strip()
            continue
        if len(buf) + len(para) + 1 > limit and buf:
            out.append(buf); buf = ""
        buf = (buf + "\n" + para).strip()
    if buf:
        out.append(buf)
    return out

def fulltext_chunks(path, slice_of=None):
    """Section-level chunks from Europe PMC open-access full text (fetch_fulltext.py).

    Each paper's abstract chunk stays in the literature layer; these add the
    body: methods, results, discussion, tables. Long sections are split so a
    chunk stays about the size of an abstract, which is what the embedder and
    the answer prompt (1400 chars shown per hit) are tuned for.
    """
    if not os.path.exists(path):
        return
    slice_of = slice_of or {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        sl = slice_of.get(f"PMID:{r['pmid']}", "pku")
        for sec in r["sections"]:
            body = sec["text"]
            if len(body) < 200:
                continue
            head = sec.get("heading") or ""
            pieces = _split(body)
            for n, piece in enumerate(pieces, 1):
                part = f" ({n}/{len(pieces)})" if len(pieces) > 1 else ""
                yield {
                    "source": "fulltext",
                    "citation_id": f"PMID:{r['pmid']}",
                    "cite_label": f"PMID:{r['pmid']}",
                    "title": (f"{r['title']} — {head}{part}" if head else f"{r['title']}{part}"),
                    "text": (f"{head}\n\n{piece}" if head else piece),
                    "year": str(r.get("year") or "")[:4],
                    "journal": "",
                    "url": f"https://europepmc.org/article/PMC/{r['pmcid']}",
                    "extra": json.dumps({"pmcid": r["pmcid"], "heading": head,
                                         "part": n, "parts": len(pieces), "slice": sl,
                                         "paper_title": r["title"]}),
                }

def market_chunks(path):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        yield {
            "source": "commons",
            "citation_id": f"Commons:{r['citation_id']}",
            "cite_label": f"Commons:{r['citation_id']}",
            "title": r["doc_title"] + (f" — {r['heading']}" if r.get("heading") else ""),
            "text": r["text"],
            "year": "",
            "journal": "",
            "url": r["provenance"],
            "extra": json.dumps({"provenance": r["provenance"], "heading": r.get("heading")}),
        }

def collect():
    chunks = []
    both = frozenset()
    ov = os.path.join(RAW, "pterin_overlap_pmids.json")
    if os.path.exists(ov):
        both = frozenset(json.load(open(ov))["pmids"])
    chunks += list(literature_chunks(os.path.join(RAW, "literature.jsonl"), "pku", both))
    seen = {c["citation_id"] for c in chunks}
    for c in literature_chunks(os.path.join(RAW, "literature_pterin.jsonl"), "pterin"):
        if c["citation_id"] not in seen:  # PKU slice wins on duplicates
            chunks.append(c); seen.add(c["citation_id"])
    chunks += list(guideline_chunks(os.path.join(RAW, "guidelines_fulltext.jsonl")))
    slice_of = {c["citation_id"]: json.loads(c["extra"]).get("slice", "pku")
                for c in chunks if c["source"] == "literature"}
    chunks += list(fulltext_chunks(os.path.join(RAW, "fulltext.jsonl"), slice_of))
    chunks += list(market_chunks(os.path.join(RAW, "market.jsonl")))
    return chunks

def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    chunks = collect()
    n = len(chunks)
    by_src, by_slice = {}, {}
    for c in chunks:
        by_src[c["source"]] = by_src.get(c["source"], 0) + 1
        if c["source"] == "literature":
            sl = json.loads(c["extra"]).get("slice", "pku")
            by_slice[sl] = by_slice.get(sl, 0) + 1
    print(f"collected {n} chunks: {by_src} slices: {by_slice}")

    # --- SQLite: chunk text + provenance ---
    db = os.path.join(OUT, "chunks.sqlite")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE chunks(
        rowid INTEGER PRIMARY KEY, source TEXT, citation_id TEXT, cite_label TEXT,
        title TEXT, text TEXT, year TEXT, journal TEXT, url TEXT, extra TEXT)""")
    con.executemany(
        "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?)",
        [(i + 1, c["source"], c["citation_id"], c["cite_label"], c["title"],
          c["text"], c["year"], c["journal"], c["url"], c["extra"])
         for i, c in enumerate(chunks)])
    con.commit(); con.close()

    # --- BM25 lexical ---
    from rank_bm25 import BM25Okapi
    tokenized = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with open(os.path.join(OUT, "bm25.pkl"), "wb") as f:
        pickle.dump({"tokenized": tokenized}, f)
    print(f"BM25 built over {n} docs")

    # --- Dense embeddings ---
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL, device="cpu")
    emb = model.encode([c["text"] for c in chunks], batch_size=64,
                       show_progress_bar=True, normalize_embeddings=True)
    emb = np.asarray(emb, dtype=np.float32)
    np.save(os.path.join(OUT, "embeddings.npy"), emb)
    print(f"embeddings: {emb.shape}")

    meta = {"version": "v0.3", "model": MODEL, "n_chunks": n, "by_source": by_src,
            "literature_by_slice": by_slice,
            "embedding_dim": int(emb.shape[1]),
            "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "build_seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=2)
    print(f"DONE in {meta['build_seconds']}s -> {OUT}")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
