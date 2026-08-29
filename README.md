# VIGIL Data Pipeline

A standalone data pipeline that collects, cleans, and (soon) labels a Bangla
harassment/cyberbullying text dataset — built to retrain the VIGIL classifier,
whose accuracy plateaued at ~57% due to a small, low-diversity training set,
not an architecture problem.

Text and label only. No usernames, profile links, or identity data are ever
stored — see [Guardrails](#guardrails-enforced-in-code) below.

---

## Status

| Stage | Status |
|---|---|
| **Extract** (YouTube comments → `raw_comments`) | ✅ Working, idempotent |
| **Clean** (normalize → emoji → lang detect → dedup → `clean_comments`) | ✅ Working, idempotent |
| **Label** (LLM-assisted labeling + human review) | 🚧 Validated (Gemma 4 26B, taxonomy tested), not yet wired into the pipeline |
| **Load / Analytics** | ⏳ Not started |

<!-- Optional: drop a terminal screenshot here showing a real run_cleaning.py output -->

---

## Directory structure (current)

```
vigil-pipeline/
├── config/
│   └── config.yaml            # API key env var name, channel + video ID list, rate limit          
├── data/
│   └── vigil.db                # SQLite DB (gitignored)
├── scripts/
│   └── validate_labeler.py    # one-off: tests LLM labeling quality before full rollout
├── src/
│   └── vigil_pipeline/
│       ├── clean/
│       |   ├── normalize.py   # Unicode NFC, strips junk invisible chars, preserves ZWNJ/ZWJ
│       |   ├── emoji.py       # extracts + strips emoji, flags threat-signal emoji
│       |   ├── lang_detect.py # bn / en / bn_en_mixed / banglish classification
│       |   └── dedup.py       # MinHash near-duplicate detection
|       ├── db/
│       |    └── schema.sql     # raw_comments + clean_comments tables
│       └── extract/
│       │   └── youtube.py     # YouTube Data API v3 comment fetcher + idempotent upsert
├── Test/
│   ├── test_upsert_idempotency.py
│   ├── test_normalize.py
│   ├── test_emoji.py
│   ├── test_lang_detect.py
│   ├── test_dedup.py
│   └── test_run_cleaning.py   # end-to-end test of the full clean pipeline
├── run_extraction.py          # loops over config.yaml channels/video_ids, mines comments
├── run_cleaning.py            # runs all 4 clean steps on new raw_comments rows
├── requirements.txt
├── .env                       # API keys (gitignored) — see Setup below
├── .gitignore
└── README.md
```

`base.py`, `cli.py`, `label/`, and `db/repository.py` are intentionally not
built yet — they get added once there are two extractors (to justify a shared
interface) and a working labeler (to justify a CLI), not before. See
[Design notes](#design-notes-worth-remembering) for why.

---

## Setup

**1. Clone/copy the project, then create a virtual environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Create a `.env` file in the project root** (no `.env.example` yet — add
one later if you want a template for others; for now just create `.env`
directly):
```
YOUTUBE_API_KEY=your_youtube_data_api_v3_key
GEMINI_API_KEY=your_google_ai_studio_key
```
- `YOUTUBE_API_KEY`: from Google Cloud Console → enable "YouTube Data API v3"
  → Credentials → Create API key → restrict it to that API only.
- `GEMINI_API_KEY`: from Google AI Studio (aistudio.google.com) → Get API key.
  Used for LLM-assisted labeling (currently via `models/gemma-4-26b-a4b-it`).

**3. Add target channels and video IDs to `config/config.yaml`:**
```yaml
youtube_api_key_env: "YOUTUBE_API_KEY"

channels:
  - id: "UCxHoBXkY88Tb8z1Ssj6CWsQ"   # Somoy TV
    category: "news"
    video_ids:
      - "REPLACE_WITH_REAL_VIDEO_ID"

db_path: "data/vigil.db"
rate_limit_sec: 1.0
```
Video IDs are added manually, one per video you want to mine — see
[Design notes](#design-notes-worth-remembering) for why this stays manual at
this scale.

---

## How to run

**Extract comments** (mines every video_id under every channel in config,
idempotent — safe to re-run, won't duplicate anything already fetched):
```bash
python run_extraction.py
```

**Clean the newly extracted comments** (normalizes, extracts emoji, detects
language mix, flags near-duplicates — only processes rows not already in
`clean_comments`):
```bash
python run_cleaning.py
```

Run these two in sequence after adding new video IDs — extraction first,
then cleaning.

**Validate the LLM labeler** (one-off — checks Gemma 4's labeling agreement
against known-correct hand-labeled examples before trusting it on the full
corpus):
```bash
python scripts/validate_labeler.py
```

**Run the test suite** (all offline, no API calls or network needed except
`tests/smoke_test_live.py`, which needs a real video ID and network access):
```bash
python tests/test_upsert_idempotency.py
python tests/test_normalize.py
python tests/test_emoji.py
python tests/test_lang_detect.py
python tests/test_dedup.py
python tests/test_run_cleaning.py
```
All should print `PASS` for every check and end with `ALL ... TESTS PASSED`.

---

## Guardrails enforced in code

- **Never stored**: usernames, display names, profile URLs, or any
  per-person/per-account derived field. Only `TEXT + LABEL` pairs.
- External YouTube comment IDs are stored **hashed** (`source_ref_hash`,
  SHA-256), not in raw form — see `test_source_ref_hash_is_not_reversible_id`
  in `test_upsert_idempotency.py`.
- Rate limiting (`rate_limit_sec` in config) and retry/backoff on 429s are
  built into the extractor, not left to chance.

---

## Design notes worth remembering

- **Raw vs. clean split**: `raw_text` is never modified (LLM labeling reads
  it, emoji included — LLMs use emoji as real context). `clean_text` has
  emoji stripped (moved to `emoji_flags`) because the classifier's tokenizer
  wasn't built to make sense of emoji tokens. Don't collapse these two paths.
- **Bangla combining marks are not punctuation.** A naive `[^\w\s]` regex
  strips Bangla vowel signs (matras) and the hasanta, corrupting words
  (কমেন্ট → কমনট). `dedup.py`'s `normalize_for_dedup` checks Unicode category
  explicitly (P*/S* only) to avoid this — see the regression test
  `test_bangla_vowel_signs_and_hasanta_are_preserved_not_stripped`.
- **The Banglish lexicon (`lang_detect.py`) and the dedup similarity
  threshold (`dedup.py`, currently 0.8) are starting heuristics, not final
  answers.** Expect to tune both once real mined volume surfaces gaps —
  same validate-then-refine principle used for the LLM labeling taxonomy.
- **`base.py` doesn't exist yet on purpose.** An abstract extractor interface
  is premature with only one extractor (YouTube); it gets built once a
  second one (the seed-dataset loader) exists and the shared shape is
  obvious from two real examples instead of a guess.
- **Video IDs are curated by hand, not auto-discovered.** Sourcing is
  deliberately targeted per class (e.g. drama/cinema comment sections for
  `sexual`, political/rivalry content for `threat`) — random or trending
  video discovery would just grow the already-dominant `bully` class faster
  than the scarce ones.
