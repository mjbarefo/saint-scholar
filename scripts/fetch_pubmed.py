from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return clean[:80] or "untitled"


def esearch_pmids(query: str, retmax: int) -> list[str]:
    resp = requests.get(
        f"{EUTILS_BASE}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "sort": "relevance",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


def efetch_articles(pmids: list[str]) -> list[dict[str, Any]]:
    if not pmids:
        return []
    resp = requests.get(
        f"{EUTILS_BASE}/efetch.fcgi",
        params={
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
        timeout=60,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    articles: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//MedlineCitation/PMID", default="").strip()
        title = (
            "".join(article.find(".//Article/ArticleTitle").itertext()).strip()
            if article.find(".//Article/ArticleTitle") is not None
            else ""
        )
        journal = article.findtext(".//Article/Journal/Title", default="").strip()
        year = (
            article.findtext(
                ".//Article/Journal/JournalIssue/PubDate/Year", default=""
            ).strip()
            or article.findtext(".//Article/ArticleDate/Year", default="").strip()
        )

        abstract_nodes = article.findall(".//Article/Abstract/AbstractText")
        abstract_parts = []
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
    pmid = article["pmid"]
    filename = f"pmid_{pmid}_{_slug(article['title'])}.md"
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PubMed abstracts and write .md + metadata."
    )
    parser.add_argument("--query", required=True, help="PubMed query string.")
    parser.add_argument(
        "--domain", required=True, help="Target domain folder under data/knowledge."
    )
    parser.add_argument("--retmax", type=int, default=10, help="Max results to fetch.")
    parser.add_argument(
        "--out", default="data/knowledge", help="Base knowledge directory."
    )
    parser.add_argument(
        "--sleep", type=float, default=0.34, help="Delay between API calls."
    )
    args = parser.parse_args()

    pmids = esearch_pmids(query=args.query, retmax=args.retmax)
    time.sleep(args.sleep)
    articles = efetch_articles(pmids)

    domain_dir = Path(args.out) / args.domain
    written = 0
    for article in articles:
        write_article(article, args.domain, domain_dir)
        written += 1

    print(
        f"Fetched {len(pmids)} PMIDs, wrote {written} markdown records to {domain_dir}"
    )


if __name__ == "__main__":
    main()
