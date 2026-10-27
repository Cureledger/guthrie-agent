#!/usr/bin/env python3
"""Guthrie corpus fetch — full text of every open-access PKU paper, from Europe PMC.

The literature layer (fetch_corpus.py) is the PubMed universe as abstracts. This
script upgrades every record in that universe that has an open-access full text
to the full paper, section by section, so Guthrie answers from methods, results
and tables, not from the summary paragraph.

Source: Europe PMC REST API (https://europepmc.org/RestfulWebService). No key.
  1. Map the universe's PMIDs -> Europe PMC records in batches of 100
     (SRC:MED AND (EXT_ID:a OR EXT_ID:b ...)). The record says whether a full
     text is held (inEPMC) and under what PMC id.
  2. Fetch <pmcid>/fullTextXML (JATS) for each one and flatten it to sections.

Accumulates like fetch_corpus.py: build/raw/fulltext.jsonl is merged by PMID,
and build/raw/fulltext_ids.txt logs every PMID whose availability has been
checked, so a re-run only looks at new records. Papers with no open-access full
text stay as abstracts in literature.jsonl; the counts land in
build/raw/fulltext_status.json so the manifest can report the split.

    python fetch_fulltext.py              # everything not yet checked (default)
    python fetch_fulltext.py --max 50     # small pull for testing
    python fetch_fulltext.py --reset      # recheck every PMID from scratch
    python fetch_fulltext.py --retry-failed   # retry ids Europe PMC had no XML for

Progress is checkpointed after every batch of 100, so an interrupted run resumes.

Universe: every PMID in build/raw/literature*.jsonl (Layer 1 PKU and Layer 1b
pterin slices alike). If none exists, the PubMed universe query from
fetch_corpus.py is run directly.
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

sys.path.insert(0, HERE)
from fetch_corpus import CORE_QUERY, esearch  # noqa: E402


def _load_ids(path):
    ids = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            t = line.strip()
            if t:
                ids.add(t)
    return ids


def _sort_key(pmid):
    return (0, int(pmid)) if pmid.isdigit() else (1, 0)


class NoFullText(Exception):
    """Europe PMC answered, but has no XML full text for this id (HTTP 4xx/500)."""


def _get(url, retries=4, timeout=90):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "guthrie-corpus"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 429/502/503/504 are transient; anything else is the service's final
            # answer for this id (Europe PMC returns 500 when an article has no
            # XML full text), so retrying only burns the rate budget.
            if e.code in (429, 502, 503, 504):
                last = e
                time.sleep(1.5 * (i + 1))
                continue
            raise NoFullText(f"HTTP {e.code}")
        except Exception as e:  # network blip, timeout
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def epmc_lookup(pmids):
    """PMIDs -> {pmid: {pmcid, in_epmc, open_access, year, title}} via one search."""
    q = "SRC:MED AND (" + " OR ".join(f"EXT_ID:{p}" for p in pmids) + ")"
    url = f"{EPMC}/search?" + urllib.parse.urlencode(
        {"query": q, "format": "json", "pageSize": 1000, "resultType": "lite"})
    data = json.loads(_get(url))
    out = {}
    for r in data.get("resultList", {}).get("result", []):
        pmid = str(r.get("pmid") or "")
        if pmid:
            out[pmid] = {"pmcid": r.get("pmcid"),
                         "in_epmc": r.get("inEPMC") == "Y",
                         "open_access": r.get("isOpenAccess") == "Y",
                         "year": r.get("pubYear"), "title": r.get("title")}
    return out


def _txt(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _table_text(tw):
    """Flatten a JATS <table-wrap> to 'caption' + one line per row, cells joined by ' | '."""
    lines = []
    cap = _txt(tw.find("caption"))
    if cap:
        lines.append(cap)
    for row in tw.iter("tr"):
        cells = [_txt(c) for c in row if c.tag in ("td", "th")]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def parse_jats(xml_bytes):
    """JATS article -> {title, sections:[{heading, text}]}; tables become their own sections."""
    root = ET.fromstring(xml_bytes)
    art = root if root.tag == "article" else root.find(".//article")
    if art is None:
        return None
    title = _txt(art.find(".//article-meta/title-group/article-title"))
    sections = []
    body = art.find(".//body")
    if body is None:
        return {"title": title, "sections": []}
    # Paragraphs that sit directly in <body> (no <sec>) still count.
    loose = [_txt(p) for p in body.findall("p")]
    loose = "\n".join(p for p in loose if p)
    if loose:
        sections.append({"heading": "", "text": loose})
    for sec in body.iter("sec"):
        head = _txt(sec.find("title"))
        paras = [_txt(p) for p in sec.findall("p")]
        text = "\n".join(p for p in paras if p)
        if text:
            sections.append({"heading": head, "text": text})
    for tw in art.iter("table-wrap"):
        t = _table_text(tw)
        if t:
            label = _txt(tw.find("label")) or "Table"
            sections.append({"heading": label, "text": t})
    return {"title": title, "sections": sections}


def fetch_fulltext(pmcid):
    return parse_jats(_get(f"{EPMC}/{pmcid}/fullTextXML"))


def _universe_pmids(lit_path):
    import glob
    paths = sorted(glob.glob(os.path.join(os.path.dirname(lit_path) or ".", "literature*.jsonl")))
    if paths:
        ids, seen = [], set()
        for path in paths:
            for line in open(path, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        pmid = str(json.loads(line).get("pmid") or "").strip()
                    except json.JSONDecodeError:
                        continue
                    if pmid and pmid not in seen:
                        ids.append(pmid); seen.add(pmid)
        return ids, ", ".join(os.path.basename(x) for x in paths)
    ids, _ = esearch(CORE_QUERY, retmax=100000)
    return [str(x) for x in ids], "PubMed query"


def _load_fulltext(path):
    have = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("pmid"):
                    have[str(r["pmid"])] = r
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0,
                    help="max PMIDs to CHECK this run (0 = all not yet checked)")
    ap.add_argument("--out", default=os.path.join(RAW, "fulltext.jsonl"))
    ap.add_argument("--literature", default=os.path.join(RAW, "literature.jsonl"))
    ap.add_argument("--reset", action="store_true",
                    help="ignore prior full-text pulls and the checked-id log")
    ap.add_argument("--sleep", type=float, default=0.2,
                    help="pause between Europe PMC requests (seconds)")
    ap.add_argument("--retry-failed", action="store_true",
                    help="recheck PMIDs listed in fulltext_failed.txt (no XML last time)")
    args = ap.parse_args()
    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    ids_path = os.path.join(out_dir, "fulltext_ids.txt")
    status_path = os.path.join(out_dir, "fulltext_status.json")
    failed_path = os.path.join(out_dir, "fulltext_failed.txt")

    have = {} if args.reset else _load_fulltext(args.out)
    checked = set() if args.reset else _load_ids(ids_path)
    no_xml = set() if args.reset else _load_ids(failed_path)
    if args.retry_failed:
        checked -= no_xml
        no_xml = set()
    universe, origin = _universe_pmids(args.literature)
    todo = [p for p in universe if p not in checked]

    def checkpoint():
        with open(args.out + ".tmp", "w") as f:
            for pmid in sorted(have, key=_sort_key):
                f.write(json.dumps(have[pmid]) + "\n")
        os.replace(args.out + ".tmp", args.out)
        with open(ids_path, "w") as f:
            for pmid in sorted(checked, key=_sort_key):
                f.write(pmid + "\n")
        with open(failed_path, "w") as f:
            for pmid in sorted(no_xml, key=_sort_key):
                f.write(pmid + "\n")
    if args.max and args.max > 0:
        todo = todo[:args.max]
    print(f"universe: {len(universe):,} PMIDs ({origin}) | full text held: {len(have):,} | "
          f"checked: {len(checked):,} | this run: {len(todo):,}", flush=True)

    added = failed = 0
    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        try:
            info = epmc_lookup(batch)
        except Exception as e:
            print(f"  lookup failed for batch at {i}: {e}", flush=True)
            continue
        for pmid in batch:
            meta = info.get(pmid) or {}
            pmcid = meta.get("pmcid")
            if meta.get("in_epmc") and pmcid:
                try:
                    doc = fetch_fulltext(pmcid)
                except NoFullText:
                    no_xml.add(pmid)  # final answer for now; --retry-failed rechecks
                    checked.add(pmid)
                    continue
                except Exception as e:
                    failed += 1
                    print(f"  {pmcid}: fetch failed ({e}); will retry next run", flush=True)
                    continue  # not marked checked, so it is retried
                if doc and doc["sections"]:
                    have[pmid] = {"pmid": pmid, "pmcid": pmcid,
                                  "title": doc["title"] or meta.get("title") or "",
                                  "year": meta.get("year"),
                                  "open_access": meta.get("open_access"),
                                  "sections": doc["sections"]}
                    added += 1
                time.sleep(args.sleep)
            checked.add(pmid)
        checkpoint()
        print(f"  {min(i + 100, len(todo)):>6}/{len(todo)} checked -> "
              f"+{added:,} full texts (held {len(have):,}, no xml {len(no_xml):,}) "
              f"{time.strftime('%H:%M:%S')}", flush=True)
        time.sleep(args.sleep)

    checkpoint()
    in_universe = set(universe)
    status = {"universe": len(universe), "checked": len(checked & in_universe),
              "full_text": len([p for p in have if p in in_universe]),
              "abstract_only": len((checked & in_universe) - set(have)),
              "no_xml_fulltext": len(no_xml & in_universe),
              "unchecked": len(in_universe - checked),
              "fetch_failures_this_run": failed,
              "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(status, open(status_path, "w"), indent=2)
    print(f"DONE: {status}")


if __name__ == "__main__":
    main()
