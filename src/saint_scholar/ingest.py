from __future__ import annotations

import json
import os
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from saint_scholar.config import (
    EMBEDDING_MODEL,
    FIGURES,
    KNOWLEDGE_CHUNK_SIZE,
    STYLE_CHUNK_OVERLAP,
    STYLE_CHUNK_SIZE,
    VECTOR_STORE_DIR,
)

load_dotenv()

_EMBEDDER: SentenceTransformer | None = None
_MANIFEST_NAME = "corpus_manifest.json"


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def _chunk_by_sentence(text: str, chunk_size_words: int) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if current and current_words + sentence_words > chunk_size_words:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = sentence_words
        else:
            current.append(sentence)
            current_words += sentence_words

    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def _chunk_style_text(text: str, target_words: int, overlap_words: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_words: list[str] = []

    def flush_chunk() -> None:
        if current_words:
            chunks.append(" ".join(current_words).strip())

    for paragraph in paragraphs:
        p_words = paragraph.split()
        if len(p_words) > target_words:
            long_parts = _chunk_by_sentence(paragraph, target_words)
            for part in long_parts:
                part_words = part.split()
                if current_words and (len(current_words) + len(part_words) > target_words):
                    flush_chunk()
                    current_words = current_words[-overlap_words:] + part_words
                else:
                    current_words.extend(part_words)
            continue

        if current_words and len(current_words) + len(p_words) > target_words:
            flush_chunk()
            current_words = current_words[-overlap_words:] + p_words
        else:
            current_words.extend(p_words)

    flush_chunk()
    return [c for c in chunks if c]


def style_richness(text: str) -> float:
    sentences = split_sentences(text)
    lengths = [len(s.split()) for s in sentences]
    length_variance = statistics.stdev(lengths) if len(lengths) > 1 else 0.0
    words = text.lower().split()
    unique_ratio = (len(set(words)) / len(words)) if words else 0.0
    return round(length_variance * unique_ratio, 3)


def get_embedding_model() -> SentenceTransformer:
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            _EMBEDDER = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
        except Exception as exc:
            raise RuntimeError(
                f"Embedding model '{EMBEDDING_MODEL}' is not available in local cache. "
                "Run ingestion once with internet access to download it."
            ) from exc
    return _EMBEDDER


def _parse_knowledge_metadata(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in [p.strip() for p in line.split("|")]:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Metadata file must contain a JSON object: {path}")
    return raw


def _normalize_metadata_values(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized


def _load_knowledge_from_txt(filepath: Path) -> tuple[str, dict[str, Any], str] | None:
    domain = filepath.parent.name
    lines = filepath.read_text(encoding="utf-8").splitlines()
    if len(lines) < 3:
        return None

    title = lines[0].strip()
    metadata_map = _parse_knowledge_metadata(lines[1].strip())
    content = "\n".join(lines[2:]).strip()
    if not content:
        return None

    metadata = {
        "source": "pubmed",
        "domain": metadata_map.get("domain", domain),
        "title": title,
        "year": metadata_map.get("year", ""),
        "pmid": metadata_map.get("pmid", ""),
        "journal": metadata_map.get("journal", ""),
        "file": filepath.name,
        "format": "txt",
    }
    return content, _normalize_metadata_values(metadata), filepath.stem


def _load_knowledge_from_md(filepath: Path) -> tuple[str, dict[str, Any], str] | None:
    content = filepath.read_text(encoding="utf-8").strip()
    if not content:
        return None

    sidecar = filepath.with_name(f"{filepath.name}.metadata.json")
    if not sidecar.exists():
        raise RuntimeError(f"Missing sidecar metadata file: {sidecar}")

    metadata_map = _read_json(sidecar)
    title = str(metadata_map.get("title", "")).strip()
    if not title:
        first_line = next((line for line in content.splitlines() if line.strip()), "")
        title = first_line.lstrip("# ").strip() or filepath.stem

    metadata = {
        "source": metadata_map.get("source", "pubmed"),
        "domain": metadata_map.get("domain", filepath.parent.name),
        "title": title,
        "year": str(metadata_map.get("year", "")),
        "pmid": str(metadata_map.get("pmid", "")),
        "journal": str(metadata_map.get("journal", "")),
        "citation_url": str(metadata_map.get("citation_url", "")),
        "authors": metadata_map.get("authors", ""),
        "file": filepath.name,
        "format": "md",
    }
    return content, _normalize_metadata_values(metadata), filepath.stem


def _load_knowledge_chunks(data_root: Path) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    knowledge_root = data_root / "knowledge"
    if not knowledge_root.exists():
        return texts, metadatas, ids

    files = sorted(knowledge_root.rglob("*.md")) + sorted(knowledge_root.rglob("*.txt"))
    for filepath in files:
        loaded: tuple[str, dict[str, Any], str] | None = None
        if filepath.suffix.lower() == ".md":
            loaded = _load_knowledge_from_md(filepath)
        elif filepath.suffix.lower() == ".txt":
            loaded = _load_knowledge_from_txt(filepath)

        if loaded is None:
            continue

        content, metadata, base_id = loaded
        chunks = _chunk_by_sentence(content, KNOWLEDGE_CHUNK_SIZE) or [content]
        for idx, chunk in enumerate(chunks, start=1):
            texts.append(chunk)
            metadatas.append(metadata)
            ids.append(f"k_{base_id}_{idx}")

    return texts, metadatas, ids


def _load_style_from_txt(filepath: Path) -> tuple[str, dict[str, Any], str] | None:
    raw = filepath.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    figure = filepath.parent.name
    metadata = {
        "source": "sacred_text",
        "figure": figure,
        "work": filepath.stem.replace("_", " ").title(),
        "file": filepath.name,
        "format": "txt",
    }
    return raw, _normalize_metadata_values(metadata), filepath.stem


def _load_style_from_md(filepath: Path) -> tuple[str, dict[str, Any], str] | None:
    raw = filepath.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    figure = filepath.parent.name

    sidecar = filepath.with_name(f"{filepath.name}.metadata.json")
    if not sidecar.exists():
        raise RuntimeError(f"Missing sidecar metadata file: {sidecar}")
    metadata_map = _read_json(sidecar)

    metadata = {
        "source": metadata_map.get("source", "sacred_text"),
        "figure": metadata_map.get("figure", figure),
        "work": metadata_map.get("work", filepath.stem.replace("_", " ").title()),
        "tradition": metadata_map.get("tradition", ""),
        "citation_url": metadata_map.get("citation_url", ""),
        "file": filepath.name,
        "format": "md",
    }
    return raw, _normalize_metadata_values(metadata), filepath.stem


def _load_style_chunks(data_root: Path) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    style_root = data_root / "style"
    if not style_root.exists():
        return texts, metadatas, ids

    files = sorted(style_root.rglob("*.md")) + sorted(style_root.rglob("*.txt"))
    for filepath in files:
        loaded: tuple[str, dict[str, Any], str] | None = None
        if filepath.suffix.lower() == ".md":
            loaded = _load_style_from_md(filepath)
        elif filepath.suffix.lower() == ".txt":
            loaded = _load_style_from_txt(filepath)

        if loaded is None:
            continue

        raw, base_metadata, base_id = loaded
        chunks = _chunk_style_text(raw, STYLE_CHUNK_SIZE, STYLE_CHUNK_OVERLAP) or [raw]
        for idx, chunk in enumerate(chunks, start=1):
            texts.append(chunk)
            metadata = dict(base_metadata)
            metadata["style_richness"] = style_richness(chunk)
            metadatas.append(metadata)
            ids.append(f"s_{metadata.get('figure', filepath.parent.name)}_{base_id}_{idx}")

    return texts, metadatas, ids


def _store_paths(kind: str) -> tuple[Path, Path]:
    root = Path(VECTOR_STORE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{kind}_meta.json", root / f"{kind}_embeddings.npy"


def _manifest_path() -> Path:
    root = Path(VECTOR_STORE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / _MANIFEST_NAME


def _file_signature(filepath: Path, data_root: Path) -> dict[str, Any]:
    stat = filepath.stat()
    return {
        "path": filepath.relative_to(data_root).as_posix(),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _corpus_manifest(data_root: Path) -> dict[str, Any]:
    knowledge_root = data_root / "knowledge"
    style_root = data_root / "style"

    knowledge_files: list[dict[str, Any]] = []
    if knowledge_root.exists():
        for filepath in sorted(knowledge_root.rglob("*")):
            if not filepath.is_file():
                continue
            suffix = filepath.suffix.lower()
            if suffix in {".md", ".txt", ".json"}:
                knowledge_files.append(_file_signature(filepath, data_root))

    style_files: list[dict[str, Any]] = []
    if style_root.exists():
        for filepath in sorted(style_root.rglob("*")):
            if not filepath.is_file():
                continue
            suffix = filepath.suffix.lower()
            if suffix in {".md", ".txt", ".json"}:
                style_files.append(_file_signature(filepath, data_root))

    return {
        "knowledge_files": knowledge_files,
        "style_files": style_files,
        "knowledge_file_count": len(knowledge_files),
        "style_file_count": len(style_files),
    }


def _load_manifest() -> dict[str, Any] | None:
    path = _manifest_path()
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw


def _save_manifest(manifest: dict[str, Any]) -> None:
    _manifest_path().write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def _save_index(
    kind: str,
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: np.ndarray,
) -> None:
    meta_path, emb_path = _store_paths(kind)
    payload = {"ids": ids, "texts": texts, "metadatas": metadatas}
    meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    np.save(str(emb_path), embeddings.astype(np.float32))


def _load_index(kind: str) -> dict[str, Any] | None:
    meta_path, emb_path = _store_paths(kind)
    if not meta_path.exists() or not emb_path.exists():
        return None

    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    embeddings = np.load(str(emb_path))
    ids = payload.get("ids", [])
    texts = payload.get("texts", [])
    metadatas = payload.get("metadatas", [])

    if not (len(ids) == len(texts) == len(metadatas) == len(embeddings)):
        raise RuntimeError(f"Corrupt vector store index for '{kind}': length mismatch.")

    return {
        "ids": ids,
        "texts": texts,
        "metadatas": metadatas,
        "embeddings": embeddings.astype(np.float32),
    }


def _normalize_embeddings(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return vectors / norms


def _compute_stats(knowledge_index: dict[str, Any], style_index: dict[str, Any]) -> dict[str, Any]:
    knowledge_metas = knowledge_index.get("metadatas", [])
    style_metas = style_index.get("metadatas", [])

    domains = Counter(m.get("domain", "unknown") for m in knowledge_metas)
    figures = Counter(m.get("figure", "unknown") for m in style_metas)
    for figure in FIGURES:
        figures.setdefault(figure, 0)

    return {
        "knowledge_total": len(knowledge_index.get("ids", [])),
        "style_total": len(style_index.get("ids", [])),
        "knowledge_by_domain": dict(domains),
        "style_by_figure": dict(figures),
    }


def ingest_if_needed(force_rebuild: bool = False) -> dict[str, Any]:
    knowledge_index = None if force_rebuild else _load_index("knowledge")
    style_index = None if force_rebuild else _load_index("style")
    data_root = Path("data")
    current_manifest = _corpus_manifest(data_root)
    stored_manifest = None if force_rebuild else _load_manifest()

    if (
        knowledge_index is not None
        and style_index is not None
        and stored_manifest == current_manifest
    ):
        print("Existing index found and corpus unchanged, skipping ingestion.")
        return {
            "knowledge_index": knowledge_index,
            "style_index": style_index,
            "embedder": get_embedding_model(),
            "stats": _compute_stats(knowledge_index, style_index),
        }

    if knowledge_index is not None and style_index is not None and stored_manifest != current_manifest:
        print("Corpus changes detected; rebuilding vector store indices.")

    knowledge_texts, knowledge_metas, knowledge_ids = _load_knowledge_chunks(data_root)
    style_texts, style_metas, style_ids = _load_style_chunks(data_root)

    if not knowledge_texts:
        auto_populate = os.getenv("SAINT_SCHOLAR_AUTO_POPULATE_KNOWLEDGE", "1").strip() != "0"
        if auto_populate:
            print("Knowledge corpus is empty. Attempting automatic PubMed bootstrap...")
            try:
                from saint_scholar.populate_knowledge import populate_knowledge_corpus

                written = populate_knowledge_corpus(
                    out_root=data_root / "knowledge",
                    per_query=12,
                    min_articles=40,
                    sleep_seconds=0.35,
                )
                print(f"Knowledge bootstrap wrote {written} article(s).")
            except Exception as exc:
                print(f"Automatic knowledge bootstrap failed: {exc}")

            knowledge_texts, knowledge_metas, knowledge_ids = _load_knowledge_chunks(data_root)
            current_manifest = _corpus_manifest(data_root)

    if not knowledge_texts or not style_texts:
        raise RuntimeError(
            "Corpus appears empty. Ensure data/style has .md/.txt files and populate data/knowledge "
            "with: python -m saint_scholar.populate_knowledge"
        )

    embedder = get_embedding_model()
    knowledge_embeddings = embedder.encode(knowledge_texts, convert_to_numpy=True)
    style_embeddings = embedder.encode(style_texts, convert_to_numpy=True)
    knowledge_embeddings = _normalize_embeddings(knowledge_embeddings)
    style_embeddings = _normalize_embeddings(style_embeddings)

    _save_index("knowledge", knowledge_ids, knowledge_texts, knowledge_metas, knowledge_embeddings)
    _save_index("style", style_ids, style_texts, style_metas, style_embeddings)
    _save_manifest(current_manifest)

    knowledge_index = _load_index("knowledge")
    style_index = _load_index("style")
    if knowledge_index is None or style_index is None:
        raise RuntimeError("Failed to load freshly created vector store indices.")

    stats = _compute_stats(knowledge_index, style_index)
    print("Saint & Scholar - Ingestion Complete")
    print(
        f"Knowledge: {stats['knowledge_total']} chunks across {len(stats['knowledge_by_domain'])} domains"
    )
    domain_bits = [f"{k}: {v}" for k, v in sorted(stats["knowledge_by_domain"].items())]
    print(f"  {' | '.join(domain_bits)}")
    print(f"Style: {stats['style_total']} chunks across {len(stats['style_by_figure'])} figures")
    figure_bits = [f"{k}: {v}" for k, v in sorted(stats["style_by_figure"].items())]
    print(f"  {' | '.join(figure_bits)}")
    print(f"Stored in {VECTOR_STORE_DIR}")

    return {
        "knowledge_index": knowledge_index,
        "style_index": style_index,
        "embedder": embedder,
        "stats": stats,
    }


if __name__ == "__main__":
    ingest_if_needed(force_rebuild=False)
