"""
Offline tests for lang_detect.py -- no network needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vigil_pipeline.clean.lang_detect import detect_lang_mix


def test_pure_bangla_detected_as_bn():
    result = detect_lang_mix("ভাই গানটা অসাধারণ হইছে")
    assert result == "bn", f"expected 'bn', got {result!r}"
    print("PASS: pure Bangla script detected as 'bn'")


def test_pure_english_detected_as_en():
    result = detect_lang_mix("This song is absolutely amazing")
    assert result == "en", f"expected 'en', got {result!r}"
    print("PASS: pure English detected as 'en'")


def test_mixed_script_detected_as_bn_en_mixed():
    result = detect_lang_mix("ভাই this গানটা is amazing")
    assert result == "bn_en_mixed", f"expected 'bn_en_mixed', got {result!r}"
    print("PASS: mixed Bangla+Latin script detected as 'bn_en_mixed'")


def test_banglish_detected_via_lexicon():
    result = detect_lang_mix("tui to ekta boka, kisu janis na")
    assert result == "banglish", f"expected 'banglish', got {result!r}"
    print("PASS: Banglish (transliterated Bangla) correctly distinguished from English")


def test_english_with_one_stray_banglish_word_stays_english():
    # Below the ratio threshold -- one matching token shouldn't flip a mostly-English sentence.
    result = detect_lang_mix(
        "I really enjoyed this movie and the soundtrack was excellent throughout bhai"
    )
    assert result == "en", f"expected 'en' (below threshold), got {result!r}"
    print("PASS: a single incidental lexicon match doesn't misclassify real English as banglish")


def test_emoji_only_text_falls_back_to_bn():
    result = detect_lang_mix("")  # simulates post-emoji-strip empty clean_text
    assert result == "bn", f"expected fallback 'bn', got {result!r}"
    print("PASS: text with no alphabetic script (e.g. post-emoji-strip empty) falls back to 'bn'")


if __name__ == "__main__":
    test_pure_bangla_detected_as_bn()
    test_pure_english_detected_as_en()
    test_mixed_script_detected_as_bn_en_mixed()
    test_banglish_detected_via_lexicon()
    test_english_with_one_stray_banglish_word_stays_english()
    test_emoji_only_text_falls_back_to_bn()
    print("\nALL LANG_DETECT TESTS PASSED")