from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Curated baseline neuroscience queries for a usable starter corpus.
DEFAULT_QUERIES = [
    ("mindfulness meditation prefrontal cortex neuroimaging", "neuroscience"),
    ("sleep memory consolidation hippocampus", "neuroscience"),
    ("neuroplasticity learning adult brain", "neuroscience"),
    ("chronic stress hippocampus prefrontal cortex", "neuroscience"),
    ("exercise neurotrophic BDNF cognition", "neuroscience"),
    ("contemplative practice attention networks fMRI", "neuroscience"),
]


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return clean[:80] or "untitled"


def _http_get(url: str, params: dict[str, Any], timeout: int = 30) -> str:
    query = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{url}?{query}"
    headers = {"User-Agent": "saint-scholar/0.1 (+https://local.dev)"}
    req = urllib.request.Request(full_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def esearch_pmids(query: str, retmax: int) -> list[str]:
    email = os.getenv("NCBI_EMAIL", "").strip()
    payload: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax,
        "sort": "relevance",
        "tool": "saint_scholar",
    }
    if email:
        payload["email"] = email
    raw = _http_get(f"{EUTILS_BASE}/esearch.fcgi", payload, timeout=30)
    data = json.loads(raw)
    return list(data.get("esearchresult", {}).get("idlist", []))


def efetch_articles(pmids: list[str]) -> list[dict[str, Any]]:
    if not pmids:
        return []
    email = os.getenv("NCBI_EMAIL", "").strip()
    payload: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": "saint_scholar",
    }
    if email:
        payload["email"] = email
    raw = _http_get(f"{EUTILS_BASE}/efetch.fcgi", payload, timeout=60)
    root = ET.fromstring(raw)

    articles: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//MedlineCitation/PMID", default="").strip()
        article_title = article.find(".//Article/ArticleTitle")
        title = "".join(article_title.itertext()).strip() if article_title is not None else ""
        journal = article.findtext(".//Article/Journal/Title", default="").strip()
        year = (
            article.findtext(".//Article/Journal/JournalIssue/PubDate/Year", default="").strip()
            or article.findtext(".//Article/ArticleDate/Year", default="").strip()
        )

        abstract_nodes = article.findall(".//Article/Abstract/AbstractText")
        abstract_parts: list[str] = []
        for node in abstract_nodes:
            label = node.attrib.get("Label", "").strip()
            text = "".join(node.itertext()).strip()
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = "\n\n".join(abstract_parts).strip()

        author_nodes = article.findall(".//Article/AuthorList/Author")
        authors: list[str] = []
        for node in author_nodes:
            last = node.findtext("LastName", default="").strip()
            initials = node.findtext("Initials", default="").strip()
            collective = node.findtext("CollectiveName", default="").strip()
            if collective:
                authors.append(collective)
            elif last:
                authors.append(f"{last} {initials}".strip())

        if pmid and title and abstract:
            articles.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "journal": journal,
                    "year": year,
                    "authors": authors,
                    "abstract": abstract,
                    "citation_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )
    return articles


def write_article(article: dict[str, Any], domain: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pmid = str(article["pmid"])
    filename = f"pmid_{pmid}_{_slug(str(article['title']))}.md"
    md_path = out_dir / filename

    md_path.write_text(
        f"# {article['title']}\n\n{article['abstract']}\n",
        encoding="utf-8",
    )

    metadata = {
        "source": "pubmed",
        "domain": domain,
        "title": article["title"],
        "pmid": pmid,
        "year": article.get("year", ""),
        "journal": article.get("journal", ""),
        "authors": article.get("authors", []),
        "citation_url": article.get("citation_url", ""),
        "license": "PubMed metadata/abstract availability varies by publisher",
    }
    (out_dir / f"{filename}.metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return md_path


def _existing_pmids(knowledge_root: Path) -> set[str]:
    pmids: set[str] = set()
    for meta_file in knowledge_root.rglob("*.metadata.json"):
        try:
            raw = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        pmid = str(raw.get("pmid", "")).strip()
        if pmid:
            pmids.add(pmid)
    return pmids


def populate_knowledge_corpus(
    out_root: Path,
    per_query: int = 12,
    min_articles: int = 40,
    sleep_seconds: float = 0.35,
) -> int:
    out_root.mkdir(parents=True, exist_ok=True)
    known_pmids = _existing_pmids(out_root)
    seen_pmids: set[str] = set(known_pmids)
    written = 0

    for query, domain in DEFAULT_QUERIES:
        if written >= min_articles:
            break

        pmids = esearch_pmids(query=query, retmax=per_query)
        new_pmids = [pmid for pmid in pmids if pmid not in seen_pmids]
        seen_pmids.update(new_pmids)
        if not new_pmids:
            time.sleep(sleep_seconds)
            continue

        articles = efetch_articles(new_pmids)
        domain_dir = out_root / domain
        for article in articles:
            pmid = str(article.get("pmid", "")).strip()
            if not pmid or pmid in known_pmids:
                continue
            write_article(article, domain, domain_dir)
            known_pmids.add(pmid)
            written += 1
            if written >= min_articles:
                break

        time.sleep(sleep_seconds)

    return written


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate data/knowledge with PubMed abstracts for Saint & Scholar."
    )
    parser.add_argument("--out", default="data/knowledge", help="Knowledge corpus root directory.")
    parser.add_argument("--per-query", type=int, default=12, help="PMIDs to request per query.")
    parser.add_argument("--min-articles", type=int, default=40, help="Minimum new records to write.")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.35,
        help="Delay between NCBI API requests in seconds.",
    )
    args = parser.parse_args()

    out_root = Path(args.out)
    written = populate_knowledge_corpus(
        out_root=out_root,
        per_query=args.per_query,
        min_articles=args.min_articles,
        sleep_seconds=args.sleep,
    )
    print(f"Knowledge population complete. Wrote {written} article(s) into {out_root}.")


if __name__ == "__main__":
    _main()
