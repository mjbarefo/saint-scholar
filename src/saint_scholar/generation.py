from __future__ import annotations

import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from saint_scholar.config import ANTHROPIC_MODEL, FIGURES, MAX_TOKENS

load_dotenv()

logger = logging.getLogger("saint_scholar.generation")


def _clip(text: str, limit: int = 1800) -> str:
    return text.strip()[:limit]


def _build_prompt(
    question: str,
    figure: str,
    knowledge_chunks: list[dict[str, Any]],
    style_chunks: list[dict[str, Any]],
) -> tuple[str, str]:
    figure_cfg = FIGURES[figure]
    figure_name = figure_cfg["name"]
    tradition = figure_cfg["tradition"]

    system_prompt = (
        "You are Saint & Scholar - a reverent teacher who explains modern scientific "
        "discoveries through the voice and wisdom of history's great spiritual and "
        "philosophical figures.\n\n"
        f"Your current voice is: {figure_name} ({tradition}).\n\n"
        "You must follow these principles:\n\n"
        "1. FACTUAL GROUNDING: ONLY state facts that are directly supported by the "
        "KNOWLEDGE PASSAGES below. Do not invent, assume, or extrapolate any "
        "scientific or medical claims beyond what the passages contain.\n\n"
        "2. REVERENT VOICE: Teach in the literary and rhetorical style demonstrated "
        "in the STYLE PASSAGES below. Mirror their sentence structures, vocabulary, "
        "tone, imagery, and teaching patterns.\n\n"
        "3. GROUNDED WONDER: Engage with the science as something genuinely "
        "marvelous, honoring both empirical understanding and contemplative reflection."
    )

    knowledge_lines: list[str] = []
    for idx, chunk in enumerate(knowledge_chunks, start=1):
        m = chunk.get("metadata", {})
        knowledge_lines.append(f"[K{idx}]: {_clip(chunk.get('text', ''))}")
        knowledge_lines.append(
            "  (Source: "
            f"{m.get('title', 'Unknown')}, {m.get('year', 'n/a')}, "
            f"{m.get('journal', 'n/a')}, PMID: {m.get('pmid', 'n/a')})"
        )
        knowledge_lines.append("")

    style_lines: list[str] = []
    for idx, chunk in enumerate(style_chunks, start=1):
        m = chunk.get("metadata", {})
        style_lines.append(f"[S{idx}]: {_clip(chunk.get('text', ''), 1200)}")
        style_lines.append(f"  (From: {m.get('work', 'Unknown')})")
        style_lines.append("")

    user_prompt = (
        "<knowledge_passages>\n"
        f"{chr(10).join(knowledge_lines)}\n"
        "</knowledge_passages>\n\n"
        f"<style_passages voice=\"{figure_name}\">\n"
        f"{chr(10).join(style_lines)}\n"
        "</style_passages>\n\n"
        "After your teaching, include a brief 'Sources' section listing which "
        "KNOWLEDGE passage IDs ([K1], [K2], etc.) support each major claim.\n\n"
        f"<user_question>\n{question.strip()}\n</user_question>"
    )

    return system_prompt, user_prompt


def generate_response(
    question: str,
    figure: str,
    knowledge_chunks: list[dict[str, Any]],
    style_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY. Add it to your .env file.")

    if figure not in FIGURES:
        raise ValueError(f"Unknown figure '{figure}'.")
    if not knowledge_chunks:
        raise ValueError("No knowledge chunks supplied to generation.")
    if not style_chunks:
        raise ValueError("No style chunks supplied to generation.")

    system_prompt, user_prompt = _build_prompt(
        question=question,
        figure=figure,
        knowledge_chunks=knowledge_chunks,
        style_chunks=style_chunks,
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = "".join(
        block.text for block in msg.content if getattr(block, "type", "") == "text"
    ).strip()

    usage = getattr(msg, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

    return {
        "response": response_text,
        "model": ANTHROPIC_MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


if __name__ == "__main__":
    test_knowledge = [
        {
            "id": "K1",
            "text": "Mindfulness practice is associated with improved prefrontal regulation.",
            "metadata": {
                "title": "Effects of Mindfulness Meditation on Prefrontal Cortex Activation",
                "year": "2022",
                "journal": "NeuroImage",
                "pmid": "12345678",
            },
        }
    ]
    test_style = [
        {
            "id": "S1",
            "text": "As rain enters an unsheltered house, so passion enters an untrained mind.",
            "metadata": {"work": "Dhammapada Excerpt"},
        }
    ]

    try:
        result = generate_response(
            question="How does meditation physically change the brain?",
            figure="buddha",
            knowledge_chunks=test_knowledge,
            style_chunks=test_style,
        )
        print(result["response"])
    except Exception as exc:
        print(f"Generation test failed: {exc}")
