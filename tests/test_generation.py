"""Unit tests for saint_scholar.generation — prompt building (no API calls)."""

from __future__ import annotations

from saint_scholar.generation import _build_prompt, _clip


class TestClip:
    def test_clips_long_text(self):
        text = "a" * 2000
        assert len(_clip(text, 100)) == 100

    def test_preserves_short_text(self):
        assert _clip("hello", 100) == "hello"

    def test_strips_whitespace(self):
        assert _clip("  hello  ") == "hello"


class TestBuildPrompt:
    def _sample_chunks(self):
        knowledge = [
            {
                "text": "Meditation changes brain structure.",
                "metadata": {
                    "title": "Effects of Meditation",
                    "year": "2023",
                    "journal": "NeuroImage",
                    "pmid": "12345",
                },
            }
        ]
        style = [
            {
                "text": "As rain enters an unsheltered house, so passion enters an untrained mind.",
                "metadata": {"work": "Dhammapada"},
            }
        ]
        return knowledge, style

    def test_returns_system_and_user_prompts(self):
        k, s = self._sample_chunks()
        system, user = _build_prompt("How does meditation work?", "buddha", k, s)
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_system_prompt_contains_figure(self):
        k, s = self._sample_chunks()
        system, _ = _build_prompt("test", "buddha", k, s)
        assert "Buddha" in system
        assert "Buddhism" in system

    def test_user_prompt_wraps_passages_in_xml_tags(self):
        k, s = self._sample_chunks()
        _, user = _build_prompt("test", "buddha", k, s)
        assert "<knowledge_passages>" in user
        assert "</knowledge_passages>" in user
        assert "<style_passages" in user
        assert "</style_passages>" in user
        assert "<user_question>" in user
        assert "</user_question>" in user

    def test_user_prompt_contains_knowledge_text(self):
        k, s = self._sample_chunks()
        _, user = _build_prompt("test", "buddha", k, s)
        assert "Meditation changes brain structure" in user

    def test_user_prompt_contains_question(self):
        k, s = self._sample_chunks()
        _, user = _build_prompt("How does meditation work?", "buddha", k, s)
        assert "How does meditation work?" in user
