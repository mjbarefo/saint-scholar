from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_legacy_metadata(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in [p.strip() for p in line.split("|")]:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def convert_knowledge_txt(path: Path) -> tuple[Path, Path]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 3:
        raise ValueError(f"Not enough lines for knowledge format: {path}")

    title = lines[0].strip()
    metadata_raw = parse_legacy_metadata(lines[1].strip())
    content = "\n".join(lines[2:]).strip()

    md_path = path.with_suffix(".md")
    md_path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")

    metadata = {
        "source": "pubmed",
        "domain": metadata_raw.get("domain", path.parent.name),
        "title": title,
        "pmid": metadata_raw.get("pmid", ""),
        "year": metadata_raw.get("year", ""),
        "journal": metadata_raw.get("journal", ""),
        "citation_url": f"https://pubmed.ncbi.nlm.nih.gov/{metadata_raw.get('pmid', '').strip()}/"
        if metadata_raw.get("pmid", "").strip()
        else "",
        "converted_from": path.name,
    }
    meta_path = path.with_name(f"{md_path.name}.metadata.json")
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return md_path, meta_path


def convert_style_txt(path: Path) -> tuple[Path, Path]:
    figure = path.parent.name
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Style file is empty: {path}")

    work = path.stem.replace("_", " ").title()
    md_path = path.with_suffix(".md")
    md_path.write_text(f"# {work}\n\n{content}\n", encoding="utf-8")

    metadata = {
        "source": "sacred_text",
        "figure": figure,
        "work": work,
        "citation_url": "",
        "converted_from": path.name,
    }
    meta_path = path.with_name(f"{md_path.name}.metadata.json")
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return md_path, meta_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert legacy .txt corpus files to .md + .md.metadata.json"
    )
    parser.add_argument("--data-root", default="data", help="Path to corpus data root.")
    parser.add_argument(
        "--delete-txt",
        action="store_true",
        help="Delete .txt after successful conversion.",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    converted = 0

    for txt in sorted((data_root / "knowledge").rglob("*.txt")):
        convert_knowledge_txt(txt)
        converted += 1
        if args.delete_txt:
            txt.unlink()

    for txt in sorted((data_root / "style").rglob("*.txt")):
        convert_style_txt(txt)
        converted += 1
        if args.delete_txt:
            txt.unlink()

    print(f"Converted {converted} files to markdown+metadata format.")


if __name__ == "__main__":
    main()
