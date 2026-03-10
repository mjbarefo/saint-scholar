from __future__ import annotations

import threading
from typing import Any

import numpy as np

from saint_scholar.config import KNOWLEDGE_TOP_K, STYLE_TOP_K
from saint_scholar.ingest import ingest_if_needed

_RESOURCES: dict[str, Any] | None = None
_RESOURCES_LOCK = threading.RLock()


def _resources() -> dict[str, Any]:
    global _RESOURCES
    with _RESOURCES_LOCK:
        if _RESOURCES is None:
            _RESOURCES = ingest_if_needed(force_rebuild=False)
        return _RESOURCES


def rebuild_resources(force_rebuild: bool = True) -> dict[str, Any]:
    global _RESOURCES
    with _RESOURCES_LOCK:
        _RESOURCES = ingest_if_needed(force_rebuild=force_rebuild)
        return _RESOURCES


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def _score(similarity: float) -> float:
    return max(0.0, min(1.0, float(similarity)))


def _query_index(
    index: dict[str, Any],
    query_embedding: np.ndarray,
    top_k: int,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ids = index["ids"]
    texts = index["texts"]
    metadatas = index["metadatas"]
    embeddings: np.ndarray = index["embeddings"]

    candidate_indices = list(range(len(ids)))
    if where:
        filtered: list[int] = []
        for i in candidate_indices:
            m = metadatas[i]
            if all(m.get(k) == v for k, v in where.items()):
                filtered.append(i)
        candidate_indices = filtered

    if not candidate_indices:
        return []

    candidate_embeddings = embeddings[candidate_indices]
    similarities = candidate_embeddings @ query_embedding
    order = np.argsort(similarities)[::-1][:top_k]

    rows: list[dict[str, Any]] = []
    for rank_idx in order:
        source_idx = candidate_indices[int(rank_idx)]
        rows.append(
            {
                "id": ids[source_idx],
                "text": texts[source_idx],
                "metadata": metadatas[source_idx],
                "score": _score(float(similarities[int(rank_idx)])),
            }
        )
    return rows


def retrieve_knowledge(question: str, top_k: int = KNOWLEDGE_TOP_K) -> list[dict[str, Any]]:
    resources = _resources()
    embedder = resources["embedder"]
    knowledge_index = resources["knowledge_index"]
    query_embedding = embedder.encode([question], convert_to_numpy=True)[0]
    query_embedding = _normalize_vector(query_embedding)
    return _query_index(knowledge_index, query_embedding, top_k=top_k)


def retrieve_style(question: str, figure: str, top_k: int = STYLE_TOP_K) -> list[dict[str, Any]]:
    resources = _resources()
    embedder = resources["embedder"]
    style_index = resources["style_index"]
    query_embedding = embedder.encode([question], convert_to_numpy=True)[0]
    query_embedding = _normalize_vector(query_embedding)
    return _query_index(style_index, query_embedding, top_k=top_k, where={"figure": figure})


def dual_retrieve(question: str, figure: str) -> dict[str, Any]:
    knowledge_chunks = retrieve_knowledge(question=question, top_k=KNOWLEDGE_TOP_K)
    style_chunks = retrieve_style(question=question, figure=figure, top_k=STYLE_TOP_K)
    return {
        "knowledge_chunks": knowledge_chunks,
        "style_chunks": style_chunks,
        "metadata": {
            "knowledge_count": len(knowledge_chunks),
            "style_count": len(style_chunks),
            "figure": figure,
            "question": question,
        },
    }


if __name__ == "__main__":
    from pprint import pprint

    pprint(dual_retrieve("How does meditation physically change the brain?", "buddha"))
