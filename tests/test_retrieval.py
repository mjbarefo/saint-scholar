"""Unit tests for saint_scholar.retrieval — pure functions only (no heavy deps)."""

from __future__ import annotations

import numpy as np

from saint_scholar.retrieval import _normalize_vector, _query_index, _score


class TestNormalizeVector:
    def test_unit_vector_unchanged(self):
        v = np.array([1.0, 0.0, 0.0])
        result = _normalize_vector(v)
        np.testing.assert_allclose(result, v)

    def test_normalizes_to_unit_length(self):
        v = np.array([3.0, 4.0])
        result = _normalize_vector(v)
        assert abs(np.linalg.norm(result) - 1.0) < 1e-6

    def test_zero_vector_returns_zero(self):
        v = np.zeros(3)
        result = _normalize_vector(v)
        np.testing.assert_array_equal(result, v)


class TestScore:
    def test_clamps_above_one(self):
        assert _score(1.5) == 1.0

    def test_clamps_below_zero(self):
        assert _score(-0.3) == 0.0

    def test_passthrough_normal_value(self):
        assert _score(0.75) == 0.75


class TestQueryIndex:
    def _make_index(self, n: int = 5, dim: int = 4):
        rng = np.random.default_rng(42)
        embeddings = rng.standard_normal((n, dim)).astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        embeddings = embeddings / norms
        return {
            "ids": [f"id_{i}" for i in range(n)],
            "texts": [f"text {i}" for i in range(n)],
            "metadatas": [{"figure": "buddha" if i % 2 == 0 else "rumi"} for i in range(n)],
            "embeddings": embeddings,
        }

    def test_returns_top_k_results(self):
        index = self._make_index(10)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = _query_index(index, query, top_k=3)
        assert len(results) == 3

    def test_results_have_required_keys(self):
        index = self._make_index()
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = _query_index(index, query, top_k=1)
        assert len(results) == 1
        r = results[0]
        assert "id" in r
        assert "text" in r
        assert "metadata" in r
        assert "score" in r

    def test_where_filter(self):
        index = self._make_index(10)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = _query_index(index, query, top_k=10, where={"figure": "buddha"})
        assert all(r["metadata"]["figure"] == "buddha" for r in results)

    def test_empty_after_filter_returns_empty(self):
        index = self._make_index(5)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = _query_index(index, query, top_k=3, where={"figure": "nonexistent"})
        assert results == []

    def test_results_sorted_by_score_descending(self):
        index = self._make_index(10)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = _query_index(index, query, top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
