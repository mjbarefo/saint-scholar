"""Batch corpus expansion — fetches real PubMed abstracts across curated neuroscience domains."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_pubmed import efetch_articles, esearch_pmids, write_article

QUERIES = [
    {
        "query": "mindfulness meditation prefrontal cortex neuroimaging",
        "domain": "neuroscience",
        "retmax": 15,
    },
    {
        "query": "sleep memory consolidation hippocampus",
        "domain": "neuroscience",
        "retmax": 15,
    },
    {
        "query": "neuroplasticity learning adult brain",
        "domain": "neuroscience",
        "retmax": 15,
    },
    {
        "query": "chronic stress hippocampus prefrontal cortex",
        "domain": "neuroscience",
        "retmax": 15,
    },
    {
        "query": "exercise neurotrophic BDNF cognition",
        "domain": "neuroscience",
        "retmax": 10,
    },
    {
        "query": "contemplative practice attention networks fMRI",
        "domain": "neuroscience",
        "retmax": 10,
    },
]

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"


def main() -> None:
    seen_pmids: set[str] = set()
    total_written = 0

    for entry in QUERIES:
        query = entry["query"]
        domain = entry["domain"]
        retmax = entry["retmax"]
        domain_dir = OUT_DIR / domain

        print(f"\n--- Query: {query!r} (domain={domain}, retmax={retmax}) ---")

        try:
            pmids = esearch_pmids(query=query, retmax=retmax)
        except Exception as exc:
            print(f"  Search failed: {exc}")
            continue

        # Deduplicate across queries
        new_pmids = [p for p in pmids if p not in seen_pmids]
        seen_pmids.update(new_pmids)

        if not new_pmids:
            print("  No new PMIDs (all duplicates).")
            continue

        time.sleep(0.4)

        try:
            articles = efetch_articles(new_pmids)
        except Exception as exc:
            print(f"  Fetch failed: {exc}")
            continue

        written = 0
        for article in articles:
            write_article(article, domain, domain_dir)
            written += 1

        total_written += written
        print(f"  Fetched {len(new_pmids)} PMIDs, wrote {written} articles.")
        time.sleep(0.4)

    print(f"\nDone. Total articles written: {total_written}")


if __name__ == "__main__":
    main()
