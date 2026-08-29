"""
Offline tests for normalize.py -- no network, no API key needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vigil_pipeline.clean.normalize import (
    normalize_text,
    strip_junk_invisible_chars,
    collapse_whitespace,
)


def test_zwnj_zwj_are_preserved():
    text_with_zwnj = "রা\u200cষ্ট্র"
    result = normalize_text(text_with_zwnj)
    assert "\u200c" in result, "ZWNJ was stripped but should be preserved (meaningful in Bangla)"
    print("PASS: ZWNJ (U+200C) is preserved")

    text_with_zwj = "ক\u200dষ"
    result = normalize_text(text_with_zwj)
    assert "\u200d" in result, "ZWJ was stripped but should be preserved (meaningful in Bangla)"
    print("PASS: ZWJ (U+200D) is preserved")


def test_junk_invisible_chars_are_removed():
    text_with_junk = "এটা একটা\u200bকমেন্ট\ufeff"
    result = strip_junk_invisible_chars(text_with_junk)
    assert "\u200b" not in result, "zero-width space should be stripped"
    assert "\ufeff" not in result, "BOM should be stripped"
    print("PASS: junk invisible characters (ZWSP, BOM) are removed")


def test_whitespace_collapses():
    messy = "এটা   একটা\n\ncomment   with\ttabs"
    result = collapse_whitespace(messy)
    assert result == "এটা একটা comment with tabs", f"unexpected: {result!r}"
    print("PASS: whitespace collapses to single spaces, no leading/trailing space")


def test_full_pipeline_on_real_looking_comment():
    raw = "  ভাই\u200b গানটা   অসাধারণ হইছে  \n"
    result = normalize_text(raw)
    assert result == "ভাই গানটা অসাধারণ হইছে", f"unexpected: {result!r}"
    print("PASS: full normalize_text pipeline produces clean, trimmed text")


if __name__ == "__main__":
    test_zwnj_zwj_are_preserved()
    test_junk_invisible_chars_are_removed()
    test_whitespace_collapses()
    test_full_pipeline_on_real_looking_comment()
    print("\nALL NORMALIZE TESTS PASSED")