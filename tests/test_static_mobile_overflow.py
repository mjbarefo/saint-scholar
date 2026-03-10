from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "saint_scholar" / "api" / "static"


def test_mobile_overflow_hardening_rules_exist() -> None:
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert ".status-section" in css
    assert ".message-header" in css
    assert ".message-body" in css
    assert ".citation-title" in css
    assert ".citation-meta" in css
    assert ".request-id" in css
    assert ".prompt-chip" in css
    assert "overflow-wrap: anywhere;" in css
    assert "word-break: break-word;" in css
    assert "@media (max-width: 480px)" in css
    assert "text-overflow: ellipsis;" in css
    assert "flex-wrap: wrap;" in css
