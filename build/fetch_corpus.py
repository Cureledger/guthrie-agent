#!/usr/bin/env python3
"""Guthrie corpus fetch — PKU literature from NCBI E-utilities.

Reproducible, key-free pull of the PKU literature universe defined in
guthrie/CORPUS.md. Writes JSONL to build/raw/. The corpus ACCUMULATES: each run
merges up to --max NEW records (deduped by PMID) into the existing
literature.jsonl and logs every attempted id in fetched_ids.txt, so repeated
runs grow it in chunks toward the whole universe instead of re-snapshotting the
most-recent N.

    python fetch_corpus.py                 # add up to 4000 more (default chunk)
    python fetch_corpus.py --max 0         # fetch ALL remaining in one run
    python fetch_corpus.py --max 500       # small pull for testing
    python fetch_corpus.py --reset         # discard prior state, start fresh
    python fetch_corpus.py --slice pterin  # Layer 1b: the pterin (BH4) and monoamine-synthesis disorders
    python fetch_corpus.py --pmids build/supplemental_pmids.txt   # explicit inclusions

Each slice has its own corpus and attempted-id log: literature.jsonl +
fetched_ids.txt for PKU, literature_pterin.jsonl + fetched_ids_pterin.txt for
the pterin slice. A pterin run also writes pterin_overlap_pmids.json, the PKU
records the pterin query matches too, which the index tags as both.
Explicit inclusions (--pmids) are papers reviewed in and listed in CORPUS.md
that the frozen universe query does not match; they merge into the PKU corpus.

No API key required. A contact email is attached when the host provides one.
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# Bump when _parse_article changes what it reads: records parsed by an older
# version are fetched again on the next run, so the fix reaches the whole
# accumulated corpus, not only new papers. 2 = whole titles (itertext).
PARSE_VERSION = 2
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

# Frozen retrieval universe (see CORPUS.md). Prioritized by pub type + recency.
CORE_QUERY = ('phenylketonuria OR phenylketonurias OR hyperphenylalaninemia '
              'OR "phenylalanine hydroxylase deficiency"')

# Layer 1b (corpus v0.2): the pterin (BH4) and monoamine-synthesis disorders,
# the sister diseases that treat the same downstream serotonin/dopamine deficit.
# Domains are listed separately in CORPUS.md; the slice is their union, minus
# anything already matched by CORE_QUERY (those records are tagged as both).
# Every multi-word term is a quoted phrase PubMed indexes as a phrase; phrases
# it would split into word-ANDs were tested and excluded.
PTERIN_DOMAINS = {
    "bh4_deficiencies": (
        '"tetrahydrobiopterin deficiency" OR "tetrahydrobiopterin deficiencies" OR '
        '"BH4 deficiency" OR "BH4 deficiencies" OR "biopterin metabolism" OR '
        '"GTP cyclohydrolase I deficiency" OR "GTP cyclohydrolase deficiency" OR '
        '"6-pyruvoyl-tetrahydropterin synthase" OR "6-pyruvoyltetrahydropterin synthase" OR '
        '"PTPS deficiency" OR "dihydropteridine reductase" OR "sepiapterin reductase deficiency" OR '
        '"pterin-4a-carbinolamine dehydratase" OR primapterinuria OR DNAJC12'),
    "dopa_responsive_dystonia": (
        '"dopa-responsive dystonia" OR "dopa responsive dystonia" OR "Segawa disease" OR '
        '"Segawa syndrome" OR "hereditary progressive dystonia"'),
    "monoamine_synthesis_disorders": (
        '"aromatic L-amino acid decarboxylase deficiency" OR "AADC deficiency" OR '
        '"tyrosine hydroxylase deficiency" OR "dopamine beta-hydroxylase deficiency" OR '
        '"monoamine neurotransmitter disorder" OR "monoamine neurotransmitter disorders" OR '
        '"pediatric neurotransmitter diseases" OR "primary neurotransmitter disorders" OR '
        '"inherited neurotransmitter disorders"'),
    "precursor_therapy": (
        '("5-hydroxytryptophan" OR oxitriptan OR levodopa OR "L-dopa" OR carbidopa OR '
        'sapropterin OR sepiapterin) AND ("tetrahydrobiopterin deficiency" OR "BH4 deficiency" OR '
        '"dopa-responsive dystonia" OR "AADC deficiency" OR "tyrosine hydroxylase deficiency" OR '
        '"monoamine neurotransmitter disorder" OR "monoamine neurotransmitter disorders" OR '
        '"dihydropteridine reductase" OR "6-pyruvoyl-tetrahydropterin synthase" OR '
        '"sepiapterin reductase")'),
    "five_htp_clinical": (
        '("5-hydroxytryptophan" OR oxitriptan) AND (depression OR depressive OR anxiety OR '
        'insomnia OR sleep OR randomized OR randomised OR placebo OR "clinical trial")'),
    "bh4_mental_health": (
        '(tetrahydrobiopterin OR BH4 OR GCH1 OR "GTP cyclohydrolase") AND (anxiety OR depression OR '
        'depressive OR "mental health" OR psychiatric OR insomnia OR sleep OR ADHD OR '
        '"attention deficit") AND (humans[mh] OR patients OR case)'),
    "monoamine_biomarkers": (
        '("homovanillic acid" OR "5-hydroxyindoleacetic acid" OR prolactin OR neopterin OR '
        '"urinary pterins" OR "CSF neurotransmitter") AND (tetrahydrobiopterin OR '
        '"monoamine neurotransmitter disorder" OR "monoamine neurotransmitter disorders" OR '
        '"dopa-responsive dystonia" OR "AADC deficiency" OR "monoamine deficiency")'),
    "gch1_vascular_pain_reviews": (
        '(GCH1 OR "GTP cyclohydrolase") AND ("blood pressure" OR endothelial OR "nitric oxide" OR '
        'pain OR hypertension) AND review[pt]'),
}
PTERIN_QUERY = " OR ".join(f"({q})" for q in PTERIN_DOMAINS.values())
PTERIN_SLICE_QUERY = f"({PTERIN_QUERY}) NOT ({CORE_QUERY}) AND 2000:3000[dp]"

# optional contact email (services work fine without it)
def _email():
    try:
        import builtins
        h = getattr(builtins, "host", None)
        if h is not None:
            return h.get_user_email()
    except Exception:
        pass
    return os.environ.get("NCBI_CONTACT_EMAIL")

def _params(extra):
    p = {"db": "pubmed", "tool": "guthrie-corpus", **extra}
    em = _email()
    if em:
        p["email"] = em
    return p

def _get(endpoint, extra, retries=4):
    url = f"{EUTILS}/{endpoint}?" + urllib.parse.urlencode(_params(extra))
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last

def esearch(query, since=None, retmax=100000):
    extra = {"term": query, "retmode": "json", "retmax": retmax,
             "sort": "pub+date", "usehistory": "y"}
    if since:
        extra["mindate"] = since
        extra["maxdate"] = "3000"
        extra["datetype"] = "edat"
    data = json.loads(_get("esearch.fcgi", extra))["esearchresult"]
    return data.get("idlist", []), int(data.get("count", 0))

def _text(el, path):
    # All the text inside the element, not just .text: PubMed marks gene and
    # chemical names up, so "Screening of <i>PAH</i> gene mutations ..." would
    # otherwise end at "Screening of".
    node = el.find(path)
    if node is None:
        return None
    return " ".join("".join(node.itertext()).split()) or None

def _parse_article(art):
    medline = art.find("MedlineCitation")
    if medline is None:
        return None
    pmid = _text(medline, "PMID")
    art_el = medline.find("Article")
    if art_el is None:
        return None
    title = _text(art_el, "ArticleTitle") or ""
    # abstract may have multiple labeled sections
    abs_parts = []
    for ab in art_el.findall("Abstract/AbstractText"):
        label = ab.get("Label")
        txt = "".join(ab.itertext()).strip()
        if txt:
            abs_parts.append(f"{label}: {txt}" if label else txt)
    abstract = "\n".join(abs_parts)
    journal = _text(art_el, "Journal/Title")
    year = (_text(art_el, "Journal/JournalIssue/PubDate/Year")
            or _text(art_el, "Journal/JournalIssue/PubDate/MedlineDate"))
    authors = []
    for a in art_el.findall("AuthorList/Author"):
        ln, fn = _text(a, "LastName"), _text(a, "Initials")
        if ln:
            authors.append(f"{ln} {fn}" if fn else ln)
    pub_types = [pt.text for pt in art_el.findall("PublicationTypeList/PublicationType") if pt.text]
    mesh = [m.text for m in medline.findall("MeshHeadingList/MeshHeading/DescriptorName") if m.text]
    doi = pmcid = None
    for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
        elif aid.get("IdType") == "pmc":
            pmcid = aid.text
    return {"pmid": pmid, "title": title, "abstract": abstract, "journal": journal,
            "year": year, "authors": authors, "pub_types": pub_types, "mesh": mesh,
            "doi": doi, "pmcid": pmcid, "parse_version": PARSE_VERSION}

def efetch_batch(pmids):
    xml = _get("efetch.fcgi", {"id": ",".join(pmids), "retmode": "xml"})
    root = ET.fromstring(xml)
    out = []
    for art in root.findall("PubmedArticle"):
        rec = _parse_article(art)
        if rec and rec.get("abstract"):  # keep only records with an abstract
            out.append(rec)
    return out

def _load_corpus(path):
    """Existing records keyed by pmid, so a run MERGES instead of overwriting."""
    have = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pmid = str(r.get("pmid") or "").strip()
                if pmid:
                    have[pmid] = r
    return have

def _load_ids(path):
    ids = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if t:
                    ids.add(t)
    return ids

def _sort_key(pmid):
    # numeric PMIDs ascending; anything odd sorts last, deterministically
    return (0, int(pmid)) if pmid.isdigit() else (1, 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=4000,
                    help="max NEW records to fetch THIS run (0 = all remaining). The "
                         "corpus accumulates across runs, so this grows it in chunks.")
    ap.add_argument("--since", default=None,
                    help="entrez date YYYY/MM/DD to restrict the universe (optional; "
                         "leave unset so growth walks the whole universe)")
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--slice", default="pku", choices=["pku", "pterin"],
                    help="which frozen universe to pull (pterin = Layer 1b, see CORPUS.md)")
    ap.add_argument("--pmids", default=None,
                    help="file of explicit PMIDs to include (one per line, # comments); "
                         "merged into the PKU corpus")
    ap.add_argument("--out", default=None,
                    help="default: raw/literature.jsonl (pku) or raw/literature_pterin.jsonl (pterin)")
    ap.add_argument("--reset", action="store_true",
                    help="ignore the existing corpus + attempted-id log; start fresh")
    args = ap.parse_args()
    pterin = args.slice == "pterin"
    if args.out is None:
        args.out = os.path.join(RAW, "literature_pterin.jsonl" if pterin else "literature.jsonl")
    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    ids_path = os.path.join(out_dir, "fetched_ids_pterin.txt" if pterin else "fetched_ids.txt")

    # Prior state (persisted between runs). `attempted` tracks every id we have
    # efetch'd, INCLUDING abstract-less ones that never enter `have` — otherwise
    # they'd be retried forever and block the chunk from advancing.
    have = {} if args.reset else _load_corpus(args.out)
    attempted = set() if args.reset else _load_ids(ids_path)

    # Records an older parser read are fetched again; one that no longer comes
    # back keeps its old record and is retried next run.
    stale = sorted((p for p, r in have.items() if r.get("parse_version") != PARSE_VERSION),
                   key=_sort_key)
    refreshed = 0
    for i in range(0, len(stale), args.batch):
        chunk = stale[i:i + args.batch]
        for r in efetch_batch(chunk):
            pmid = str(r.get("pmid") or "").strip()
            if pmid in have:
                have[pmid] = r
                refreshed += 1
        print(f"  re-read {min(i + args.batch, len(stale)):>6}/{len(stale)} older records "
              f"-> {refreshed:,} refreshed", flush=True)
        time.sleep(0.34)  # NCBI ~3 req/s without a key

    if args.pmids:
        # Explicit inclusions: every listed paper not already held, no cap.
        universe = [ln.split("#")[0].strip() for ln in open(args.pmids, encoding="utf-8")]
        universe = [i for i in universe if i]
        total = len(universe)
        todo = [i for i in universe if i not in have]
    else:
        query = PTERIN_SLICE_QUERY if pterin else CORE_QUERY
        universe, total = esearch(query, since=args.since, retmax=100000)
        universe = [str(x) for x in universe]
        todo = [i for i in universe if i not in attempted]
        if args.max and args.max > 0:
            todo = todo[:args.max]
    if pterin:
        # PKU records the pterin query also matches: the index tags them "pku,pterin".
        both, _ = esearch(f"({PTERIN_QUERY}) AND ({CORE_QUERY})", retmax=100000)
        with open(os.path.join(out_dir, "pterin_overlap_pmids.json"), "w") as f:
            json.dump({"pmids": sorted((str(x) for x in both), key=_sort_key)}, f)

    print(f"[{args.slice}{' + explicit' if args.pmids else ''}] universe: {total:,} match | have: {len(have):,} records | "
          f"attempted: {len(attempted):,} | this run: {len(todo):,} "
          f"(cap={args.max or 'ALL'}, since={args.since})", flush=True)

    added = 0
    for i in range(0, len(todo), args.batch):
        chunk = todo[i:i + args.batch]
        for r in efetch_batch(chunk):
            pmid = str(r.get("pmid") or "").strip()
            if pmid:
                have[pmid] = r
                added += 1
        attempted.update(chunk)
        print(f"  {min(i + args.batch, len(todo)):>6}/{len(todo)} ids -> "
              f"+{added:,} new (corpus {len(have):,})", flush=True)
        time.sleep(0.34)  # NCBI ~3 req/s without a key

    with open(args.out, "w") as f:
        for pmid in sorted(have, key=_sort_key):
            f.write(json.dumps(have[pmid]) + "\n")
    with open(ids_path, "w") as f:
        for pmid in sorted(attempted, key=_sort_key):
            f.write(pmid + "\n")

    remaining = sum(1 for i in universe if i not in attempted)
    tail = (" Corpus is COMPLETE for this universe."
            if remaining == 0 else
            f" Re-run to fetch the next {min(args.max or remaining, remaining):,}.")
    print(f"DONE: corpus {len(have):,} records (+{added:,} this run, "
          f"{refreshed:,} re-read); "
          f"universe {total:,}, attempted {len(attempted):,}, remaining {remaining:,}.{tail}")

if __name__ == "__main__":
    main()
