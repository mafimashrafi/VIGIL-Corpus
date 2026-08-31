<div align="center">

# 🛡️ VIGIL Data Pipeline

### Mining, cleaning, and labeling real Bangla comments — to teach a harassment-detection model what harassment actually looks like.

</div>

---

A standalone data pipeline that collects, cleans, and labels a Bangla
harassment/cyberbullying text dataset — built to retrain the VIGIL classifier
(a Chrome extension that scans live pages for bullying/harassment/spam),
whose accuracy plateaued at ~57% due to a small, low-diversity training set,
not an architecture problem.

**Privacy by design**: this project stores TEXT + LABEL pairs only. No
usernames, profile links, or any per-person/per-account data is ever
collected or derived — see [Guardrails](#guardrails-enforced-in-code).

---

## Status

| Stage | Status |
|---|---|
| **Extract** (YouTube comments → `raw_comments`) | ✅ Working, idempotent |
| **Clean** (normalize → emoji → lang detect → dedup → `clean_comments`) | ✅ Working, idempotent |
| **Label** (LLM-assisted labeling via Gemma 4, + free label propagation to duplicates) | ✅ Working, idempotent |
| **Human review sampler** | ⏳ Not started |
| **Load / final export for classifier retraining** | ⏳ Not started |

Currently spending a few days mining and reviewing real comment volume
before moving to human review and export.

---

## How the pipeline actually works, file by file

This is the real call chain — which file reads what, calls what, and writes
what, in the order it happens:

```
1. EXTRACT
   ┌─────────────────────┐
   │  run_extraction.py   │  (project root)
   └──────────┬───────────┘
              │ reads: .env (YOUTUBE_API_KEY), config/config.yaml (channels + video_ids)
              │ calls: src/vigil_pipeline/extract/youtube.py
              │         → fetch_comments()  -- hits YouTube Data API v3
              │         → upsert_comment()  -- idempotent insert (content_hash)
              ▼
      data/vigil.db :: raw_comments table
      (schema defined in src/vigil_pipeline/db/schema.sql)


2. CLEAN
   ┌─────────────────────┐
   │  run_cleaning.py     │  (project root)
   └──────────┬───────────┘
              │ reads: raw_comments rows not yet in clean_comments
              │ calls, in order, from src/vigil_pipeline/clean/:
              │   1. normalize.py    -- Unicode NFC, strips junk invisible chars
              │   2. emoji.py        -- extracts + strips emoji -> emoji_flags
              │   3. lang_detect.py  -- bn / en / bn_en_mixed / banglish
              │   4. dedup.py        -- MinHash near-duplicate detection
              │                        (grouped by source + calendar day)
              ▼
      data/vigil.db :: clean_comments table


3. LABEL
   ┌─────────────────────┐
   │  run_llm_labeler.py  │  (project root)
   └──────────┬───────────┘
              │ reads: .env (GEMINI_API_KEY), config/config.yaml (rate_limit_sec)
              │        clean_comments rows where is_near_dup = 0 and not yet labeled
              │ calls: src/vigil_pipeline/label/llm_labeler.py
              │         → call_gemma()  -- sends RAW text (emoji included) to
              │                            Gemma 4, using prompts.py's taxonomy,
              │                            with a responseSchema forcing valid
              │                            JSON output matching the 6 labels
              │         → label_new_comments()      -- writes to labels table
              │         → propagate_labels_to_duplicates()
              │                                     -- copies labels to near-dup
              │                                        comments at zero API cost
              ▼
      data/vigil.db :: labels table


 (one-off, not part of the regular run)
   ┌───────────────────────────┐
   │ scripts/validate_labeler.py│
   └─────────────┬───────────────┘
              tests Gemma's labeling agreement against a small hand-labeled
              set BEFORE trusting it on real volume. Not run automatically --
              re-run this manually any time the taxonomy prompt changes.
```

**Why this order, and not some other order**: schema and taxonomy were
decided before any extractor code existed. Extraction was proven on a single
video before scaling to more. Cleaning was built and tested module-by-module
(normalize → emoji → lang_detect → dedup) before being wired into one
runner. Labeling was validated on a small hand-labeled batch (via
`validate_labeler.py`) before being pointed at real, unlabeled volume. Each
stage only reads what the previous stage already finished — nothing runs
speculatively ahead of proven-correct data.

---

## Directory structure (current)

```
Vigil_corpus/
├── config/
│   └── config.yaml              # API key env var names, channel + video ID list, rate limit
├── data/
│   └── vigil.db                  # SQLite DB (gitignored)
├── src/
│   └── vigil_pipeline/
│       ├── db/
│       │   └── schema.sql       # raw_comments, clean_comments, labels tables
│       ├── extract/
│       │   └── youtube.py       # YouTube Data API v3 fetcher + idempotent upsert
│       ├── clean/
│       │   ├── normalize.py     # Unicode NFC, strips junk invisible chars, preserves ZWNJ/ZWJ
│       │   ├── emoji.py         # extracts + strips emoji, flags threat-signal emoji
│       │   ├── lang_detect.py   # bn / en / bn_en_mixed / banglish classification
│       │   └── dedup.py         # MinHash near-duplicate detection
│       └── label/
│           ├── prompts.py       # the labeling taxonomy prompt (single source of truth)
│           └── llm_labeler.py   # Gemma 4 API calls, candidate selection, label propagation
├── scripts/
│   └── validate_labeler.py      # one-off: validates LLM labeling quality before trusting it
├── tests/
│   ├── test_upsert_idempotency.py
│   ├── test_normalize.py
│   ├── test_emoji.py
│   ├── test_lang_detect.py
│   ├── test_dedup.py
│   ├── test_run_cleaning.py     # end-to-end test of the full clean pipeline
│   └── test_llm_labeler.py      # end-to-end test of the full labeling pipeline
├── run_extraction.py            # loops over config.yaml channels/video_ids, mines comments
├── run_cleaning.py              # runs all 4 clean steps on new raw_comments rows
├── run_llm_labeler.py           # runs LLM labeling + duplicate label propagation
├── requirements.txt
├── .env                         # API keys (gitignored)
├── .gitignore
└── README.md
```

Not built yet, on purpose: `base.py` (no shared extractor interface until a
second extractor exists to justify one), `cli.py` (no unified CLI until all
stages are stable), `db/repository.py` (no SQL abstraction layer until the
duplicated raw SQL across files actually becomes painful to maintain). See
[Design notes](#design-notes-worth-remembering) for the reasoning.

---

## Setup

**1. Create a virtual environment and install dependencies:**
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Create a `.env` file in the project root:**
```
YOUTUBE_API_KEY=your_youtube_data_api_v3_key
GEMINI_API_KEY=your_google_ai_studio_key
```
- `YOUTUBE_API_KEY`: Google Cloud Console → enable "YouTube Data API v3" →
  Credentials → Create API key → restrict it to that API only.
- `GEMINI_API_KEY`: Google AI Studio (aistudio.google.com) → Get API key.
  Used for LLM-assisted labeling via `models/gemma-4-26b-a4b-it`.

**3. Add target channels and video IDs to `config/config.yaml`:**
```yaml
youtube_api_key_env: "YOUTUBE_API_KEY"

channels:
  - id: "UCxHoBXkY88Tb8z1Ssj6CWsQ"   # Somoy TV
    category: "news"
    video_ids:
      - "REPLACE_WITH_REAL_VIDEO_ID"

db_path: "data/vigil.db"
rate_limit_sec: 0.20
```
Video IDs are added manually, one per video you want to mine, curated
deliberately per category rather than auto-discovered — see
[Design notes](#design-notes-worth-remembering).

---

## How to operate this project

Run the three stages in order. Each is idempotent — safe to re-run any time,
never reprocesses or duplicates work already done.

**1. Extract** — mine comments from every video_id in config:
```bash
python run_extraction.py
```

**2. Clean** — normalize, extract emoji, detect language mix, flag near-duplicates:
```bash
python run_cleaning.py
```

**3. Label** — send clean, non-duplicate comments to Gemma 4, then propagate
labels to duplicates for free:
```bash
python run_llm_labeler.py
```
This prints live progress per comment (`[12/567] id=45: ['bully'] (confidence=0.9)`),
since batches can take 30+ minutes on real volume. Safe to interrupt with
Ctrl+C at any point — every successful label is committed immediately, and
the run simply picks up where it left off next time.

**Validate the labeler** (run this once before trusting it on new volume, or
again any time the taxonomy prompt in `prompts.py` changes):
```bash
python scripts/validate_labeler.py
```

**Check progress at any time**, even mid-run, from a second terminal:
```bash
sqlite3 data/vigil.db "SELECT COUNT(*) FROM labels;"
sqlite3 data/vigil.db "SELECT label, COUNT(*) FROM labels GROUP BY label ORDER BY COUNT(*) DESC;"
```

**Run the test suite** (all offline, no API calls or network needed except
`tests/smoke_test_live.py`):
```bash
python tests/test_upsert_idempotency.py
python tests/test_normalize.py
python tests/test_emoji.py
python tests/test_lang_detect.py
python tests/test_dedup.py
python tests/test_run_cleaning.py
python tests/test_llm_labeler.py
```
All should print `PASS` for every check and end with `ALL ... TESTS PASSED`.

---

## Guardrails enforced in code

- **Never stored**: usernames, display names, profile URLs, or any
  per-person/per-account derived field. Only `TEXT + LABEL` pairs.
- External YouTube comment IDs are stored **hashed** (`source_ref_hash`,
  SHA-256), not in raw form.
- Rate limiting (`rate_limit_sec` in config) and retry/backoff on network
  errors and 429s are built into both the extractor and the labeler.
- `labels` never records anything about a person or account — it labels
  *text*, never "this user is a bully."

---

## Design notes worth remembering

- **Raw vs. clean split**: `raw_text` is never modified. The LLM labeler
  reads `raw_text` (emoji included — LLMs use emoji as real context).
  `clean_text` has emoji stripped (moved to `emoji_flags`) because the
  classifier's tokenizer wasn't built to make sense of emoji tokens.
- **Bangla combining marks are not punctuation.** A naive `[^\w\s]` regex
  strips Bangla vowel signs (matras) and the hasanta, corrupting words
  (কমেন্ট → কমনট). `dedup.py`'s normalizer checks Unicode category
  explicitly (punctuation/symbol only) to avoid this — caught by a real bug
  during development, now locked in by a regression test.
- **The Banglish lexicon and the dedup similarity threshold (0.8) are
  starting heuristics, not final answers** — expect to tune both as real
  mined volume surfaces gaps.
- **Near-duplicates are never sent to the LLM.** Once a canonical comment is
  labeled, its near-duplicates inherit the same label via a SQL join, at
  zero additional API cost.
- **`responseSchema` constrains but doesn't fully guarantee clean output.**
  Even with a JSON schema forcing the model's output shape, Gemma
  occasionally still leaks a stray markdown code fence around otherwise-valid
  JSON. The labeler defensively tries direct parsing, then fence-stripping,
  then substring extraction, before giving up and safely retrying next run.
- **Video sourcing is curated by hand, targeted per label category** — news
  content over-produces `bully`/`not_harassment` and under-produces
  `sexual`/`religious`/`spam`; drama/cinema, religious content, and
  political-rivalry content are deliberately sourced to correct that
  imbalance, rather than mining more of what's already abundant.
- **`base.py`, `cli.py`, and `db/repository.py` don't exist yet, on purpose.**
  Each gets built once a second real example (a second extractor, a stable
  multi-stage flow, painful SQL duplication) makes the right abstraction
  obvious — not before, and not as a guess.

---

## A note on how this project was built

This project was built as a learning exercise, with AI assistance (Claude)
used throughout as a pair-programming and design-review partner — not to
generate the project unattended. Every architectural decision (schema
design, taxonomy, sourcing strategy, build order), every line of code, and
every debugging session was reviewed, tested, and understood by me before
being kept. Real bugs were hit and fixed along the way — a Bangla text
corruption bug in the deduplication step, a database corruption from an
interrupted run, an LLM API silently wrapping valid JSON in markdown — and
working through each of them was as much the point of this project as the
final pipeline itself. If you're a recruiter or reviewer: I can walk through
any part of this system and explain not just what it does, but why it's
built this way.

---

## Contributing

This is a learning project, but contributions, suggestions, and critiques
are genuinely welcome — whether that's expanding the Banglish lexicon,
improving the labeling taxonomy, tightening the dedup logic, or pointing out
something that's wrong. Open an issue or a pull request; if you're
Bangladeshi and have thoughts on the labeling categories or sourcing
strategy specifically, your perspective is especially appreciated.
