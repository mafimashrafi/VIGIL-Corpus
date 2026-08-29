"""
Offline tests for emoji.py -- no network needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vigil_pipeline.clean.emoji import (
    extract_emoji,
    strip_emoji,
    emoji_flags_json,
    has_threat_signal_emoji,
    process_emoji,
)


def test_extract_emoji_finds_all_emoji_in_order():
    text = "ভাই গানটা 🔥🔥🔥 অসাধারণ 😂"
    result = extract_emoji(text)
    assert result == ["🔥", "🔥", "🔥", "😂"], f"unexpected: {result}"
    print("PASS: extract_emoji finds all emoji in order")


def test_strip_emoji_removes_emoji_keeps_text_clean():
    text = "ভাই গানটা 🔥🔥🔥 অসাধারণ 😂"
    result = strip_emoji(text)
    assert result == "ভাই গানটা অসাধারণ", f"unexpected: {result!r}"
    print("PASS: strip_emoji removes emoji and collapses resulting whitespace")


def test_emoji_only_comment_strips_to_empty_string():
    text = "😂😂😂😂😂"
    result = strip_emoji(text)
    assert result == "", f"expected empty string, got: {result!r}"
    print("PASS: emoji-only comment strips to empty clean_text (expected -- flag separately, don't drop raw_text)")


def test_emoji_flags_json_returns_none_when_no_emoji():
    result = emoji_flags_json([])
    assert result is None, f"expected None, got {result!r}"
    print("PASS: emoji_flags_json returns None (not empty string) when no emoji present")


def test_emoji_flags_json_serializes_correctly():
    result = emoji_flags_json(["🔥", "😂"])
    assert result == '["🔥", "😂"]', f"unexpected: {result!r}"
    print("PASS: emoji_flags_json serializes to valid JSON string")


def test_threat_signal_emoji_detected():
    assert has_threat_signal_emoji(["🔪", "😂"]) is True
    assert has_threat_signal_emoji(["😂", "🔥"]) is False
    print("PASS: threat-signal emoji correctly detected as a pre-filter flag")


def test_zwj_family_emoji_extracted_as_single_unit():
    # Family emoji is 4 codepoints joined by ZWJ -- must be treated as ONE emoji,
    # not split into 4 separate characters (which would also corrupt the ZWJ
    # that normalize.py deliberately preserves elsewhere).
    text = "সুন্দর পরিবার 👨‍👩‍👧‍👦"
    result = extract_emoji(text)
    assert len(result) == 1, f"expected 1 combined emoji, got {len(result)}: {result}"
    print("PASS: multi-codepoint ZWJ emoji sequence treated as a single emoji, not split")


def test_process_emoji_full_pipeline():
    text = "তোরে দেখে নিব 🔪"
    clean, emojis, threat_flag = process_emoji(text)
    assert clean == "তোরে দেখে নিব"
    assert emojis == ["🔪"]
    assert threat_flag is True
    print("PASS: process_emoji returns clean text, emoji list, and threat flag together")


if __name__ == "__main__":
    test_extract_emoji_finds_all_emoji_in_order()
    test_strip_emoji_removes_emoji_keeps_text_clean()
    test_emoji_only_comment_strips_to_empty_string()
    test_emoji_flags_json_returns_none_when_no_emoji()
    test_emoji_flags_json_serializes_correctly()
    test_threat_signal_emoji_detected()
    test_zwj_family_emoji_extracted_as_single_unit()
    test_process_emoji_full_pipeline()
    print("\nALL EMOJI TESTS PASSED")