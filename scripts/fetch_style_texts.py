"""Fetch public-domain style texts from Project Gutenberg.

Writes .md + .metadata.json sidecar pairs into data/style/<figure>/.
All sources are plain-text files hosted on gutenberg.org.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "style"

# ── Configuration ────────────────────────────────────────────────────────────
# Each figure maps to a list of Gutenberg works to fetch.
# Fields:
#   id          – Gutenberg ebook number
#   work_title  – human-readable title for metadata
#   tradition   – tradition label
#   slug        – filename prefix (auto-derived from work_title if absent)

FIGURES: dict[str, dict[str, Any]] = {
    "aurelius": {
        "name": "Marcus Aurelius",
        "tradition": "Stoicism",
        "works": [
            {"id": 2680, "work_title": "Meditations (Long)"},
            {"id": 15877, "work_title": "Thoughts of Marcus Aurelius"},
        ],
    },
    "buddha": {
        "name": "Buddha",
        "tradition": "Buddhism",
        "works": [
            {"id": 2017, "work_title": "Dhammapada (Muller)"},
            {"id": 35185, "work_title": "Dhammapada (Woodward)"},
            {"id": 35895, "work_title": "Gospel of Buddha (Carus)"},
            {"id": 8920, "work_title": "Light of Asia (Arnold)"},
        ],
    },
    "laotzu": {
        "name": "Lao Tzu",
        "tradition": "Taoism",
        "works": [
            {"id": 216, "work_title": "Tao Te Ching (Legge)"},
            {"id": 59709, "work_title": "Chuang Tzu (Giles)"},
        ],
    },
    "rumi": {
        "name": "Rumi",
        "tradition": "Sufism",
        "works": [
            {"id": 61724, "work_title": "Masnavi (Redhouse)"},
            {"id": 45159, "work_title": "Persian Mystics – Rumi (Davis)"},
            {"id": 57068, "work_title": "Festival of Spring (Hastie)"},
        ],
    },
    "solomon": {
        "name": "Solomon",
        "tradition": "Wisdom Literature",
        "works": [
            {"id": 8021, "work_title": "Ecclesiastes (KJV)"},
            {"id": 8020, "work_title": "Proverbs (KJV)"},
            {"id": 8022, "work_title": "Song of Solomon (KJV)"},
            {"id": 8325, "work_title": "Wisdom of Solomon (Douay-Rheims)"},
        ],
    },
    # ── New figures ──────────────────────────────────────────────────────────
    "epictetus": {
        "name": "Epictetus",
        "tradition": "Stoicism",
        "works": [
            {"id": 45109, "work_title": "Enchiridion"},
            {"id": 10661, "work_title": "Discourses of Epictetus"},
            {"id": 871, "work_title": "Golden Sayings of Epictetus"},
        ],
    },
    "seneca": {
        "name": "Seneca",
        "tradition": "Stoicism",
        "works": [
            {"id": 56075, "work_title": "Morals – Happy Life, Benefits, Anger"},
            {"id": 3794, "work_title": "On Benefits (Seneca)"},
        ],
    },
    "confucius": {
        "name": "Confucius",
        "tradition": "Confucianism",
        "works": [
            {"id": 3330, "work_title": "Analects (Legge)"},
            {"id": 10056, "work_title": "Chinese Literature Anthology"},
        ],
    },
    "krishna": {
        "name": "Krishna",
        "tradition": "Hinduism",
        "works": [
            {"id": 2388, "work_title": "Bhagavad-Gita (Arnold)"},
        ],
    },
    "upanishads": {
        "name": "The Upanishads",
        "tradition": "Vedanta",
        "works": [
            {"id": 3283, "work_title": "Upanishads (Muller)"},
        ],
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────────

GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt"
GUTENBERG_ALT = "https://www.gutenberg.org/files/{eid}/{eid}-0.txt"
CHUNK_WORDS = 1500


def _clean_gutenberg(text: str) -> str:
    """Strip Project Gutenberg header/footer boilerplate."""
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
        "End of the Project Gutenberg",
        "End of Project Gutenberg",
    ]
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            nl = text.find("\n", idx)
            text = text[nl + 1 :] if nl != -1 else text[idx + len(marker) :]
            break
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
            break
    return text.strip()


def _write_excerpt(
    figure_dir: Path,
    filename: str,
    content: str,
    metadata: dict[str, Any],
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    md_path = figure_dir / filename
    md_path.write_text(content, encoding="utf-8")
    meta_path = figure_dir / f"{filename}.metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote {md_path.name} ({len(content):,} chars)")


def _fetch_gutenberg(eid: int) -> str:
    """Download a Gutenberg plain-text file, trying two URL patterns."""
    for url_template in (GUTENBERG_URL, GUTENBERG_ALT):
        url = url_template.format(eid=eid)
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            continue
    raise RuntimeError(f"Could not fetch Gutenberg #{eid} from either URL pattern")


def _slugify(title: str) -> str:
    """Convert a work title to a filename-safe slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:60]


def _chunk_text(text: str, max_words: int = CHUNK_WORDS) -> list[str]:
    """Split text into chunks of approximately max_words words."""
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ── Main fetch logic ─────────────────────────────────────────────────────────


def fetch_figure(figure_key: str) -> None:
    """Fetch all works for one figure, chunk them, and write .md + metadata."""
    cfg = FIGURES[figure_key]
    name = cfg["name"]
    tradition = cfg["tradition"]
    fig_dir = DATA_DIR / figure_key

    print(f"\n{'=' * 60}")
    print(f"  {name} ({tradition})")
    print(f"{'=' * 60}")

    for work in cfg["works"]:
        eid = work["id"]
        title = work["work_title"]
        slug = work.get("slug") or _slugify(title)

        print(f"\n  Fetching Gutenberg #{eid}: {title}")
        try:
            raw = _fetch_gutenberg(eid)
        except RuntimeError as exc:
            print(f"    SKIP — {exc}")
            continue

        text = _clean_gutenberg(raw)
        if len(text) < 500:
            print(f"    SKIP — cleaned text too short ({len(text)} chars)")
            continue

        chunks = _chunk_text(text)
        print(f"    {len(text):,} chars -> {len(chunks)} chunk(s)")

        for i, chunk in enumerate(chunks):
            part = f"_part{i + 1}" if len(chunks) > 1 else ""
            filename = f"{slug}{part}.md"
            heading = f"{title}, Part {i + 1}" if len(chunks) > 1 else title
            _write_excerpt(
                fig_dir,
                filename,
                f"# {heading}\n\n{chunk}\n",
                {
                    "source": "gutenberg",
                    "gutenberg_id": eid,
                    "figure": figure_key,
                    "work": title,
                    "tradition": tradition,
                    "citation_url": f"https://www.gutenberg.org/ebooks/{eid}",
                },
            )

        # Be polite to Gutenberg servers
        time.sleep(1)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch style-corpus texts from Project Gutenberg.")
    parser.add_argument(
        "--figure",
        choices=list(FIGURES.keys()),
        help="Fetch texts for a single figure only.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="fetch_all",
        help="Fetch texts for all figures.",
    )
    args = parser.parse_args()

    if not args.figure and not args.fetch_all:
        parser.print_help()
        print("\nSpecify --figure <name> or --all.")
        return

    targets = [args.figure] if args.figure else list(FIGURES.keys())

    for key in targets:
        fetch_figure(key)

    print(f"\nDone. Fetched {len(targets)} figure(s).")


if __name__ == "__main__":
    main()
