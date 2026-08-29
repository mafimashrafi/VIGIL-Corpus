"""
Offline tests for dedup.py -- no network needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vigil_pipeline.clean.dedup import find_near_duplicates, normalize_for_dedup, get_shingles


def test_normalize_for_dedup_strips_punctuation_and_case():
    result = normalize_for_dedup("Wow!! This is GREAT...")
    assert result == "wow this is great", f"unexpected: {result!r}"
    print("PASS: normalize_for_dedup lowercases and strips punctuation")


def test_shingles_on_short_text():
    result = get_shingles("hi", k=3)
    assert result == {"hi"}, f"unexpected: {result}"
    print("PASS: text shorter than shingle size returns itself as a single shingle")


def test_exact_duplicate_comments_flagged():
    records = [
        {"id": 1, "text": "কমেন্ট রেখে গেলাম, পরে আবার আসব"},
        {"id": 2, "text": "কমেন্ট রেখে গেলাম, পরে আবার আসব"},
    ]
    dup_map = find_near_duplicates(records)
    assert dup_map == {2: 1}, f"unexpected: {dup_map}"
    print("PASS: exact duplicate text flagged, first occurrence stays canonical")


def test_near_duplicate_with_minor_variation_flagged():
    records = [
        {"id": 1, "text": "কমেন্ট রেখে গেলাম, পরে আবার আসব ভাই"},
        {"id": 2, "text": "কমেন্ট রেখে গেলাম, পরে আবার আসব"},  # missing one word, otherwise identical
    ]
    dup_map = find_near_duplicates(records)
    assert dup_map == {2: 1}, f"unexpected: {dup_map}"
    print("PASS: near-duplicate with minor variation (one word dropped) still flagged")


def test_bangla_vowel_signs_and_hasanta_are_preserved_not_stripped():
    text = "কমেন্ট রেখে গেলাম"
    result = normalize_for_dedup(text)
    assert "কমেন্ট" in result.split()[0] or result.startswith("কমেন্ট"), (
        f"Bangla word corrupted -- vowel signs/hasanta were stripped: {result!r}"
    )
    assert result == "কমেন্ট রেখে গেলাম", f"unexpected corruption: {result!r}"
    print("PASS: Bangla vowel signs and hasanta survive normalize_for_dedup unmodified")


def test_distinct_comments_not_flagged():
    records = [
        {"id": 1, "text": "ভাই গানটা অসাধারণ হইছে"},
        {"id": 2, "text": "রাজনীতি নিয়ে আমার কোনো আগ্রহ নাই"},
    ]
    dup_map = find_near_duplicates(records)
    assert dup_map == {}, f"expected no duplicates, got {dup_map}"
    print("PASS: genuinely distinct comments are not flagged as duplicates")


def test_three_way_dedup_chain_all_point_to_first():
    records = [
        {"id": 1, "text": "who's watching in 2026 like this comment"},
        {"id": 2, "text": "who's watching in 2026 like this comment!!"},
        {"id": 3, "text": "whos watching in 2026 like this comment"},
    ]
    dup_map = find_near_duplicates(records)
    assert dup_map.get(2) == 1, f"unexpected: {dup_map}"
    assert dup_map.get(3) == 1, f"unexpected: {dup_map}"
    print("PASS: multiple near-duplicates in a spam burst all point back to the same canonical id")


if __name__ == "__main__":
    test_normalize_for_dedup_strips_punctuation_and_case()
    test_shingles_on_short_text()
    test_exact_duplicate_comments_flagged()
    test_near_duplicate_with_minor_variation_flagged()
    test_bangla_vowel_signs_and_hasanta_are_preserved_not_stripped()
    test_distinct_comments_not_flagged()
    test_three_way_dedup_chain_all_point_to_first()
    print("\nALL DEDUP TESTS PASSED")