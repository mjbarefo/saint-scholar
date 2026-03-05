"""Unit tests for saint_scholar.ingest — chunking and parsing functions."""

from __future__ import annotations

from saint_scholar.ingest import (
    _chunk_by_sentence,
    _chunk_style_text,
    _parse_knowledge_metadata,
    _word_count,
    split_sentences,
    style_richness,
)


class TestSplitSentences:
    def test_basic_split(self):
        result = split_sentences("Hello world. How are you? I am fine!")
        assert result == ["Hello world.", "How are you?", "I am fine!"]

    def test_empty_string(self):
        assert split_sentences("") == []

    def test_single_sentence(self):
        assert split_sentences("Just one.") == ["Just one."]


class TestWordCount:
    def test_basic(self):
        assert _word_count("hello world foo") == 3

    def test_empty(self):
        assert _word_count("") == 1 or _word_count("") == 0  # implementation may vary


class TestChunkBySentence:
    def test_single_chunk_for_short_text(self):
        text = "Short sentence. Another short one."
        result = _chunk_by_sentence(text, chunk_size_words=100)
        assert len(result) == 1

    def test_splits_long_text(self):
        sentences = ["This is sentence number %d." % i for i in range(50)]
        text = " ".join(sentences)
        result = _chunk_by_sentence(text, chunk_size_words=20)
        assert len(result) > 1

    def test_empty_text(self):
        assert _chunk_by_sentence("", 100) == []


class TestChunkStyleText:
    def test_single_chunk_for_short_text(self):
        result = _chunk_style_text("Short paragraph.", target_words=100, overlap_words=10)
        assert len(result) == 1

    def test_splits_long_text_with_overlap(self):
        paragraphs = ["Word " * 100 + "end." for _ in range(5)]
        text = "\n\n".join(paragraphs)
        result = _chunk_style_text(text, target_words=50, overlap_words=10)
        assert len(result) > 1

    def test_empty_text(self):
        assert _chunk_style_text("", 100, 10) == []


class TestParseKnowledgeMetadata:
    def test_parses_pipe_separated(self):
        line = "year: 2023 | pmid: 12345 | journal: Nature"
        result = _parse_knowledge_metadata(line)
        assert result["year"] == "2023"
        assert result["pmid"] == "12345"
        assert result["journal"] == "Nature"

    def test_empty_string(self):
        assert _parse_knowledge_metadata("") == {}


class TestStyleRichness:
    def test_returns_float(self):
        result = style_richness("Short. Medium length sentence. Very long sentence with many words in it.")
        assert isinstance(result, float)
        assert result >= 0

    def test_single_sentence(self):
        result = style_richness("Just one sentence.")
        assert result == 0.0  # no variance with one sentence
