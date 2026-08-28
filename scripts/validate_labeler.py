"""
Validation script: tests Gemma 4's labeling quality on a small batch BEFORE
you commit to labeling the full comment corpus with it.

Includes the known tricky cases we identified: religious devotional bait,
spam engagement templates, emoji-only comments, and Banglish (Latin-script Bangla).

Setup:
    pip install requests python-dotenv
    Add to .env:  GEMINI_API_KEY=your_key_here

Usage:
    python validate_labeler.py
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL = "models/gemma-4-26b-a4b-it"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:generateContent"

TAXONOMY_PROMPT = """You are a content moderation classifier for Bangla (Bengali) social media comments.
Classify the comment into one or more of these labels:

- bully: insults, mockery, name-calling, or demeaning language directed at a person or group.
- sexual: sexual harassment, sexually explicit or objectifying comments directed at someone.
- religious: comments that attack, mock, or threaten someone/some group BECAUSE of their religion.
  IMPORTANT: expressions of religious devotion or engagement-bait ("if you love the Prophet, comment")
  are NOT religious harassment. Only label "religious" if the comment attacks or demeans based on religion.
- threat: explicit or implied threats of violence or harm against a person or group.
- spam: generic, repetitive, template-like comments meant to farm engagement or promote something,
  regardless of topic (e.g. "who's watching in 2026, like this comment", "commenting so I can find this later").
- not_harassment: none of the above -- includes neutral comments, praise, devotional expressions,
  genuine discussion, or ordinary reactions (including emoji-only reactions with no targeted harm).

A comment can have multiple labels if applicable. Emoji should be read as part of the meaning
(e.g. knife/skull emoji directed at a person can indicate "threat"; laughing emoji at someone's
expense can indicate "bully"). An emoji-only reaction with no clear target is "not_harassment".

Respond with ONLY a JSON object, no other text, in this exact format:
{"labels": ["label1", "label2"], "confidence": 0.0}

Comment: "{comment}"
"""

# Known tricky cases from earlier testing, plus placeholders -- replace/add real
# mined comments here to reach 30-50 total before running a real validation pass.
TEST_SET = [
    {"text": "নবীকে ভালোবাসেন তাহলে কমেন্ট করেন", "human_label": ["not_harassment"]},
    {"text": "কমেন্ট রেখে গেলাম, যতবার কেও লাইক দিবে ততবার এসে এই গান শুনব", "human_label": ["spam"]},
    {"text": "কে কে ২০২৬ এ শুনতেছেন লাইক করেন", "human_label": ["spam"]},
    {"text": "😂😂😂😂😂", "human_label": ["not_harassment"]},
    {"text": "tui to ekta beshi boka, kisu janish na", "human_label": ["bully"]},  # Banglish
    {"text": "তোরে মাইরা ফেলবো দেখা হইলে", "human_label": ["threat"]},
    {"text": "তুই একটা মাল, তোর মতো মেয়েদের রাস্তায় দেখলেই বোঝা যায়", "human_label": ["sexual", "bully"]},
    {"text": "ভাই গানটা অসাধারণ হইছে", "human_label": ["not_harassment"]},
    # --- add ~20-40 more real mined comments here before treating this as final ---
]


def call_gemma(comment: str, api_key: str, retries: int = 3):
    prompt = TAXONOMY_PROMPT.replace("{comment}", comment)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    for attempt in range(retries):
        resp = requests.post(f"{API_URL}?key={api_key}", headers=headers, json=payload, timeout=20)
        if resp.status_code == 429:
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = raw_text.strip().strip("`").replace("json", "", 1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse model output: {raw_text!r}")
            return {"labels": [], "confidence": 0.0}
    raise RuntimeError("Max retries exceeded")


def run_validation():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in .env")
        return

    agreements = 0
    mismatches = []

    for i, case in enumerate(TEST_SET, 1):
        result = call_gemma(case["text"], api_key)
        predicted = sorted(result.get("labels", []))
        expected = sorted(case["human_label"])
        agreed = predicted == expected

        status = "MATCH" if agreed else "MISMATCH"
        print(f"[{i}] {status}")
        print(f"    text:      {case['text']}")
        print(f"    human:     {expected}")
        print(f"    gemma:     {predicted}  (confidence: {result.get('confidence')})")

        if agreed:
            agreements += 1
        else:
            mismatches.append(case["text"])

        time.sleep(1)  # basic rate limiting

    total = len(TEST_SET)
    rate = (agreements / total) * 100 if total else 0
    print(f"\n{'='*50}")
    print(f"Agreement rate: {agreements}/{total} = {rate:.1f}%")
    if mismatches:
        print("\nReview these mismatches to see if it's a prompt/taxonomy issue:")
        for m in mismatches:
            print(f"  - {m}")

    print("\nGuideline: below ~80% agreement, revise the taxonomy prompt before scaling up.")


if __name__ == "__main__":
    run_validation()