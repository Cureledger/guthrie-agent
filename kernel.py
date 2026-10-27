"""Guthrie — PKU retrieval brain (kernel sidecar).

Loaded automatically when the `guthrie` skill is loaded. Exposes:

    pku_search(query, k=8, source=None)  -> list[dict]  ranked chunks + citations
    pku_ask(question, k=8, mode="brief") -> dict         grounded, cited answer
    pku_paper(ref)                       -> dict          one paper, full text if open
    pku_concerns()                       -> list[dict]    the literature slices, with paper counts
    guthrie_index_info()                 -> dict          index build metadata

Design contract (see CORPUS.md):
  * CITE OR REFUSE. Every literature claim carries a [PMID:xxxx]; every market
    claim a [Commons:doc]. If retrieval is weak, Guthrie says so instead of
    inventing a citation.
  * NO medical advice / diagnosis / dosing for an individual. Guthrie reports
    what the literature says and routes care decisions to a clinician.
  * Literature passages carry a slice tag: Layer 1 (PKU) or Layer 1b (the
    pterin/BH4 and monoamine-synthesis disorders). Pterin passages are labelled
    (literature/pterin, ...) in context and the system prompt requires Guthrie to
    name the disease and never pass a pterin finding off as a PKU finding.
  * The index is local: BM25 + MiniLM dense, score-fused. It is located via
    $GUTHRIE_INDEX_DIR, else the `pku_index/` folder beside this file. If it is
    missing, run guthrie/build/{fetch_corpus,build_market_layer,build_index}.py
    or unpack the pku_index_v0.tar.gz artifact there.

This module is written to pass the skill-sidecar gate: only imports, defs, and
literal constants at top level; all computed state lives inside functions.
"""
import os
import re

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Softened from 0.35: the hard pre-LLM refusal on the top hit's raw dense cosine
# was rejecting genuine in-corpus questions (esp. filler-wrapped ones). 0.30 lets
# borderline queries reach the LLM, which still cite-or-refuses over the actual
# passages, while clearly off-topic (< ~0.25) is still short-circuited cheaply.
DEFAULT_MIN_RELEVANCE = 0.30
# Leading conversational/meta phrases that carry no topical signal but dilute the
# query embedding — "find a source about ...", "tell me about ...", "look ..." —
# were pushing real questions under the relevance gate. normalize_query() peels
# them, then additively expands common abbreviations so lexical + dense both
# match the full terms.
LEADING_FILLER = (
    r"^\s*(?:"
    r"please|can you|could you|would you|"
    r"i(?:'d| would)? (?:like|want)(?: to)?(?: know)?|i need|help me|"
    r"find(?: me)?|search(?: for)?|look(?: for| up)?|dig up|hunt for|"
    r"tell me(?: about)?|talk to me about|teach me(?: about)?|"
    r"explain|describe|summari[sz]e|do you know(?: about)?|"
    r"show me|give me|list|"
    r"what(?:'s| is| are| does| do)|"
    r"a|any|some|the|"
    r"sources?|papers?|studies?|articles?|references?|citations?|evidence|"
    r"literature|research|info(?:rmation)?|"
    r"about|on|for|regarding|into"
    r")\b[\s,:\-]*"
)
ABBREV_EXPANSIONS = (
    (r"\bphe\b", "phe phenylalanine"),
    (r"\bpku\b", "pku phenylketonuria"),
    (r"\bbh4\b", "bh4 tetrahydrobiopterin"),
    (r"\bpah\b", "pah phenylalanine hydroxylase"),
    (r"\blnaas?\b", "large neutral amino acids"),
    (r"\bgmp\b", "glycomacropeptide"),
)
MEDICAL_PATTERN = (
    r"\b(should i|my (child|kid|son|daughter|baby)|my (phe|level)s?\b|"
    r"how much .*(should|can) (i|we|my)|is it safe for (me|my)|"
    r"what dose|change (my|our|the) (dose|diet)|stop taking)\b")
GUTHRIE_SYSTEM = (
    "You are Guthrie, the PKU community research agent, named for Robert Guthrie "
    "(newborn-screening heel-prick test, 1963). You answer strictly from the "
    "CONTEXT passages provided, which are retrieved from the PKU literature "
    "(PubMed) and the PKU Commons infrastructure. RULES: "
    "(1) Cite every factual claim inline using the bracket label shown on each "
    "passage, e.g. [PMID:12345678] or [Commons:leaderboard]. "
    "(2) Never invent a citation or a PMID. If the context does not support an "
    "answer, say you do not have a grounded source and suggest the PKU Commons "
    "blog or a clinician. "
    "(3) You do not give medical advice, diagnosis, or dosing for an individual; "
    "you explain what the literature reports and defer care decisions to a "
    "clinician. "
    "(4) Passages labelled (literature/pterin, ...) come from the sister "
    "tetrahydrobiopterin (BH4) and monoamine-synthesis disorders, not from PKU. "
    "You may use them to explain shared mechanism, biomarkers, and how those "
    "disorders are treated, but you must say which disease the passage is about "
    "and never present a pterin-disorder finding as a PKU finding. "
    "(5) Be concise and direct. No em-dashes.")


def guthrie_state():
    """Lazy module-level cache (non-underscore name so the sidecar gate allows it)."""
    g = globals()
    if "GUTHRIE_STATE" not in g:
        g["GUTHRIE_STATE"] = {"loaded": False}
    return g["GUTHRIE_STATE"]


def index_dir():
    """Locate the index: $GUTHRIE_INDEX_DIR, else pku_index/ beside this file."""
    d = os.environ.get("GUTHRIE_INDEX_DIR")
    if d:
        return d
    import sys
    here = os.path.dirname(sys._getframe().f_code.co_filename)
    return os.path.join(here or ".", "pku_index")


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def normalize_query(query):
    """Peel leading conversational filler and expand common PKU abbreviations.

    "find a source about at home phe monitor" -> "at home phe phenylalanine
    monitor". Filler carries no topical signal but lowers the query embedding's
    similarity to every passage, which false-refuses genuine questions. We strip
    stacked leading filler, then additively expand abbreviations (kept alongside
    the original token so both lexical and dense retrieval benefit). Returns the
    original text if peeling would leave almost nothing (e.g. "look harder").
    """
    s = (query or "").strip()
    for _ in range(8):  # peel stacked filler ("find" + "a" + "source" + "about")
        n = re.sub(LEADING_FILLER, "", s, count=1, flags=re.I)
        if n == s:
            break
        s = n.strip()
    if len(s) < 3:
        s = (query or "").strip()
    for pat, rep in ABBREV_EXPANSIONS:
        s = re.sub(pat, rep, s, flags=re.I)
    return s


def load_index():
    """Load the SQLite chunks, embeddings, BM25 corpus, and embed model once.
    Serialized: concurrent first requests must not each append to the state."""
    st = guthrie_state()
    if st.get("loaded"):
        return st
    import threading
    lock = st.setdefault("lock", threading.Lock())
    with lock:
        if st.get("loaded"):
            return st
        return _load_index_locked(st)


def _load_index_locked(st):
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_XET_DISABLE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import json, pickle, sqlite3
    import numpy as np
    idx = index_dir()
    dbp = os.path.join(idx, "chunks.sqlite")
    if not os.path.exists(dbp):
        raise FileNotFoundError(
            f"Guthrie index not found at {idx}. Build it "
            "(guthrie/build/*.py) or set GUTHRIE_INDEX_DIR to a prebuilt copy.")
    con = sqlite3.connect(dbp)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT rowid, source, citation_id, cite_label, title, text, year, "
        "journal, url, extra FROM chunks ORDER BY rowid")]
    con.close()
    for r in rows:  # literature slice tag ("pku" | "pterin" | "pku,pterin"), see CORPUS.md Layer 1b
        try:
            extra = json.loads(r.get("extra") or "{}")
        except Exception:
            extra = {}
        r["slice"] = extra.get("slice") or ""
        # A full-text chunk is titled "<paper> — <section> (n/m)"; callers that
        # list sources want the paper's own title.
        r["paper_title"] = extra.get("paper_title") or r["title"]
    emb = np.load(os.path.join(idx, "embeddings.npy"))
    with open(os.path.join(idx, "bm25.pkl"), "rb") as f:
        tokenized = pickle.load(f)["tokenized"]
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer
    st.update(rows=rows, emb=emb, bm25=BM25Okapi(tokenized),
              model=SentenceTransformer(EMBED_MODEL, device="cpu"),
              meta=json.load(open(os.path.join(idx, "meta.json"))),
              loaded=True)
    return st


def minmax(x):
    import numpy as np
    x = np.asarray(x, dtype=np.float32)
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def _slice_ok(row_slice, wanted):
    """A row passes when any of its slice tags is wanted. Rows with no tag
    (guidelines, commons) always pass."""
    if not wanted or not row_slice:
        return True
    return any(t in wanted for t in row_slice.split(","))


def pku_search(query, k=8, source=None, alpha=0.5, slices=None):
    """Hybrid retrieval. Returns k chunks ranked by fused BM25 + dense score.

    alpha  = dense weight (0 = pure lexical, 1 = pure semantic).
    source = optional filter: 'literature' | 'fulltext' | 'guideline_fulltext' | 'commons'.
    slices = optional list of concern tags ('pku', 'pterin', ...): only passages
             from those concerns are returned (untagged guideline/commons rows
             always pass). This is the per-member concern filter.
    Each result carries its citation label + url so the caller can cite it.
    The raw dense cosine is kept per hit (used as the absolute relevance gate).
    """
    import numpy as np
    st = load_index()
    rows, emb, bm25, model = st["rows"], st["emb"], st["bm25"], st["model"]
    query = normalize_query(query)
    bm_scores = np.asarray(bm25.get_scores(tokenize(query)), dtype=np.float32)
    q_emb = model.encode([query], normalize_embeddings=True)[0].astype(np.float32)
    dense = emb @ q_emb  # cosine (rows are L2-normalized)
    fused = alpha * minmax(dense) + (1 - alpha) * minmax(bm_scores)
    out = []
    for i in np.argsort(-fused):
        r = rows[int(i)]
        if source and r["source"] != source:
            continue
        if not _slice_ok(r.get("slice") or "", slices):
            continue
        out.append({
            "rank": len(out) + 1, "citation": r["cite_label"], "source": r["source"],
            "slice": r.get("slice") or "",
            "title": r["title"], "paper_title": r.get("paper_title") or r["title"],
            "year": r["year"], "journal": r["journal"],
            "url": r["url"], "text": r["text"],
            "score": round(float(fused[int(i)]), 4),
            "dense": round(float(dense[int(i)]), 4),
            "bm25": round(float(bm_scores[int(i)]), 4)})
        if len(out) >= k:
            break
    return out


def format_context(hits):
    blocks = []
    for h in hits:
        src = h["source"]
        if h.get("slice") and h["slice"] != "pku":
            src = f"{src}/{h['slice']}"
        head = f"[{h['citation']}] ({src}, {h['year']}) {h['title']}".strip()
        blocks.append(f"{head}\n{h['text'][:1400]}")
    return "\n\n---\n\n".join(blocks)


def get_host():
    """Resolve the injected `host` singleton (kernel global, or up the stack)."""
    if "host" in globals():
        return globals()["host"]
    import inspect
    for fr in inspect.stack():
        h = fr.frame.f_globals.get("host")
        if h is not None:
            return h
    return None


def pku_ask(question, k=8, mode="brief", min_relevance=DEFAULT_MIN_RELEVANCE, llm=None,
            slices=None):
    """Grounded, cited answer. mode: 'brief' | 'full'.

    slices = optional literature slices to answer from (see pku_search).

    Returns {answer, citations, hits, refused, medical_flag}. Refuses (no
    fabricated citation) when retrieval is weak.

    Relevance is judged on the top hit's RAW dense cosine (not the min-max fused
    score, whose top is ~1.0 for any query). On-topic PKU questions score
    ~0.55-0.70; off-topic questions score < 0.25. Default gate 0.35.

    The grounding LLM is injectable so the SAME refusal + citation logic runs in
    every deployment. `llm` is a callable (prompt, system, max_tokens) -> {text}.
    If None, it falls back to the injected host.llm (inside Claude Science). The
    standalone HTTP service (serve/serve.py) passes an Anthropic-API llm here so
    it is literally this code path, not a reimplementation.
    """
    if llm is None:
        host = get_host()
        if host is not None:
            llm = lambda prompt, system, max_tokens: host.llm(
                prompt, system=system, max_tokens=max_tokens)
    hits = pku_search(question, k=k, slices=slices)
    top = hits[0]["dense"] if hits else -1.0
    medical = bool(re.search(MEDICAL_PATTERN, question, re.I))

    if not hits or top < min_relevance:  # weak-retrieval refusal
        return {"answer": ("I do not have a grounded source for that in the PKU "
                           "corpus. Try rephrasing, or see the PKU Commons blog / "
                           "a metabolic clinician. I will not guess a citation."),
                "citations": [], "hits": hits, "refused": True, "medical_flag": medical}

    disclaimer = ("\n\nNote: this is what the literature reports, not medical "
                  "advice for your situation. Dosing and diet changes are "
                  "decisions for your metabolic clinician.") if medical else ""
    length = "2-4 sentences" if mode == "brief" else "a thorough, well-structured answer"
    prompt = (f"CONTEXT (each passage is prefixed with its citation label):\n\n"
              f"{format_context(hits)}\n\nQUESTION: {question}\n\n"
              f"Answer in {length}, citing inline with the bracket labels above. "
              f"If the context is insufficient, say so plainly.")

    if llm is None:  # offline (e.g. eval without an LLM) — retrieval only
        return {"answer": None, "citations": [h["citation"] for h in hits],
                "hits": hits, "refused": False, "medical_flag": medical,
                "note": "no LLM available; returning retrieval only"}

    resp = llm(prompt, system=GUTHRIE_SYSTEM,
               max_tokens=900 if mode == "full" else 400)
    text = (resp.get("text") or "").strip() + disclaimer
    cited = sorted(set(re.findall(r"\[(?:PMID:\d+|Commons:[a-z0-9\-]+)\]", text)))
    return {"answer": text, "citations": cited, "hits": hits,
            "refused": False, "medical_flag": medical}


EPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# Human labels for the concern tags in the index (CORPUS.md layers). A tag
# with no label here is shown by its raw key.
CONCERN_LABELS = {
    "pku": "PKU",
    "pterin": "BH4 and monoamine disorders",
}


def pku_concerns():
    """The concerns (index slices) a member can pick, with paper counts."""
    meta = load_index()["meta"]
    by_slice = meta.get("literature_by_slice") or {}
    counts = {}
    for tag, n in by_slice.items():
        for t in tag.split(","):
            counts[t] = counts.get(t, 0) + n
    return [{"key": t, "label": CONCERN_LABELS.get(t, t), "papers": n}
            for t, n in sorted(counts.items(), key=lambda x: -x[1])]


def pku_paper(ref, max_chars=0):
    """Pull ONE paper into the session for discussion: full text when it is open
    access, otherwise the abstract. `ref` is a PMID ("12345678" or "PMID:12345678"),
    a PMC id ("PMC1234567"), or a DOI. Live call to Europe PMC; no key.

    Returns {pmid, pmcid, doi, title, year, journal, abstract, sections,
             full_text (bool), url, citation}. `sections` is [{heading, text}]
    (tables included, flattened). max_chars > 0 truncates the body for very
    long papers. Raises nothing on a miss: full_text is False and sections [].
    """
    import json, urllib.parse, urllib.request
    ref = str(ref).strip()
    low = ref.lower()
    if low.startswith("pmid:"):
        ref = ref[5:].strip()
    if low.startswith("pmc"):
        q = f"PMCID:{ref.upper()}"
    elif ref.isdigit():
        q = f"EXT_ID:{ref} AND SRC:MED"
    else:
        q = f'DOI:"{ref}"'
    url = f"{EPMC_REST}/search?" + urllib.parse.urlencode(
        {"query": q, "format": "json", "pageSize": 1, "resultType": "core"})
    with urllib.request.urlopen(url, timeout=60) as r:
        hits = json.load(r).get("resultList", {}).get("result", [])
    if not hits:
        return {"pmid": None, "pmcid": None, "doi": None, "title": None, "year": None,
                "journal": None, "abstract": None, "sections": [], "full_text": False,
                "url": None, "citation": None, "note": f"no Europe PMC record for {ref}"}
    h = hits[0]
    import html
    def _clean(t):  # Europe PMC 'core' fields carry escaped HTML (<i>, <h4>)
        return re.sub(r"<[^>]+>", "", html.unescape(t)).strip() if t else t
    pmid, pmcid = h.get("pmid"), h.get("pmcid")
    out = {"pmid": pmid, "pmcid": pmcid, "doi": h.get("doi"), "title": _clean(h.get("title")),
           "year": h.get("pubYear"), "journal": h.get("journalTitle"),
           "abstract": _clean(h.get("abstractText")), "sections": [], "full_text": False,
           "url": (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid
                   else f"https://europepmc.org/article/PMC/{pmcid}"),
           "citation": f"PMID:{pmid}" if pmid else f"PMC:{pmcid}"}
    if h.get("inEPMC") == "Y" and pmcid:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "build"))
        try:
            from fetch_fulltext import fetch_fulltext
            doc = fetch_fulltext(pmcid)
        except Exception as e:  # 500s happen for a few PMC ids; abstract still returned
            out["note"] = f"full text fetch failed: {e}"
            doc = None
        if doc and doc["sections"]:
            secs = doc["sections"]
            if max_chars and max_chars > 0:
                kept, used = [], 0
                for sec in secs:
                    if used >= max_chars:
                        break
                    t = sec["text"][:max_chars - used]
                    kept.append({"heading": sec["heading"], "text": t}); used += len(t)
                secs = kept
            out["sections"], out["full_text"] = secs, True
    return out


def guthrie_index_info():
    """Return index build metadata (model, chunk counts, build time)."""
    return load_index()["meta"]
