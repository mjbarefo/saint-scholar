"""Integration tests for the FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from saint_scholar.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "saint-scholar-api"
        assert "status" in data
        assert "checks" in data

    def test_health_reports_checks(self):
        response = client.get("/health")
        data = response.json()
        assert "vector_store" in data["checks"]
        assert "anthropic_key" in data["checks"]


class TestFiguresEndpoint:
    def test_figures_returns_200(self):
        response = client.get("/v1/figures")
        assert response.status_code == 200
        data = response.json()
        assert "figures" in data
        assert isinstance(data["figures"], dict)

    def test_figures_includes_buddha(self):
        response = client.get("/v1/figures")
        data = response.json()
        assert "buddha" in data["figures"]


class TestAskEndpointValidation:
    def test_empty_question_rejected(self):
        response = client.post("/v1/ask", json={"question": "", "figure": "buddha"})
        assert response.status_code == 422

    def test_unknown_figure_rejected(self):
        response = client.post(
            "/v1/ask", json={"question": "Hello", "figure": "nonexistent_figure_xyz"}
        )
        assert response.status_code == 422

    def test_missing_figure_rejected(self):
        response = client.post("/v1/ask", json={"question": "Hello"})
        assert response.status_code == 422


class TestHomeEndpoint:
    def test_home_returns_html(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
