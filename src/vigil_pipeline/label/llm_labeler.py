import json
import time
import sqlite3
import requests
from datetime import datetime, timezone

from prompts import TAXONOMY_PROMPT

MODEL = "models/gemma-4-26b-a4b-it"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:generateContent"


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["bully", "sexual", "religious", "threat", "spam", "not_harassment"],
            },
        },
        "confidence": {"type": "number"},
    },
    "required": ["labels", "confidence"],
}


def call_gemma(comment: str, api_key: str, retries: int = 5) -> dict:
    prompt = TAXONOMY_PROMPT.replace("{comment}", comment)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    headers = {"Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            resp = requests.post(f"{API_URL}?key={api_key}", headers=headers, json=payload, timeout=60)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 2 ** attempt  
            print(f"  [WARN] Network error ({type(e).__name__}), retrying in {wait}s "
                  f"(attempt {attempt + 1}/{retries})...")
            time.sleep(wait)
            continue

        if resp.status_code == 429:
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            print(f"  [WARN] Still unparseable despite responseSchema -- raw output: {raw_text[:200]!r}")
            return {"labels": [], "confidence": 0.0}

    print(f"  [WARN] Gave up after {retries} attempts due to network errors -- will retry on next run.")
    return {"labels": [], "confidence": 0.0}


def fetch_labelable_rows(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        """
        SELECT r.id AS raw_comment_id, r.raw_text
        FROM raw_comments r
        JOIN clean_comments c ON c.raw_comment_id = r.id
        LEFT JOIN labels l ON l.raw_comment_id = r.id AND l.label_source = 'llm_assisted'
        WHERE c.is_near_dup = 0
          AND l.raw_comment_id IS NULL
        """
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def label_new_comments(
    conn: sqlite3.Connection,
    api_key: str,
    call_fn=call_gemma,
    rate_limit_sec: float = 1.0,
) -> dict:
    rows = fetch_labelable_rows(conn)
    print(f"  Found {len(rows)} candidate comment(s) to label.")
    labeled_count = 0
    skipped_unparseable = 0

    for i, row in enumerate(rows, 1):
        try:
            result = call_fn(row["raw_text"], api_key)
        except Exception as e:
            print(f"  [{i}/{len(rows)}] WARN: unexpected error on row {row['raw_comment_id']}: {e} -- skipping, will retry next run.")
            skipped_unparseable += 1
            continue

        labels = result.get("labels", [])
        confidence = result.get("confidence")

        if not labels:
            print(f"  [{i}/{len(rows)}] id={row['raw_comment_id']}: unparseable output, skipping (will retry next run)")
            skipped_unparseable += 1
            continue

        now = datetime.now(timezone.utc).isoformat()
        for label in labels:
            conn.execute(
                """
                INSERT OR IGNORE INTO labels
                    (raw_comment_id, label, label_source, confidence, reviewed, created_at)
                VALUES (?, ?, 'llm_assisted', ?, 0, ?)
                """,
                (row["raw_comment_id"], label, confidence, now),
            )
        labeled_count += 1
        conn.commit()
        print(f"  [{i}/{len(rows)}] id={row['raw_comment_id']}: {labels} (confidence={confidence})")
        time.sleep(rate_limit_sec)

    return {
        "candidates": len(rows),
        "labeled": labeled_count,
        "skipped_unparseable": skipped_unparseable,
    }


def propagate_labels_to_duplicates(conn: sqlite3.Connection) -> int:
    pairs = conn.execute(
        """
        SELECT raw_comment_id AS dup_id, dup_of_id AS canonical_id
        FROM clean_comments
        WHERE is_near_dup = 1 AND dup_of_id IS NOT NULL
        """
    ).fetchall()

    propagated = 0
    now = datetime.now(timezone.utc).isoformat()

    for dup_id, canonical_id in pairs:
        canonical_labels = conn.execute(
            "SELECT label, confidence FROM labels WHERE raw_comment_id = ? AND label_source = 'llm_assisted'",
            (canonical_id,),
        ).fetchall()

        for label, confidence in canonical_labels:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO labels
                    (raw_comment_id, label, label_source, confidence, reviewed, created_at)
                VALUES (?, ?, 'llm_assisted', ?, 0, ?)
                """,
                (dup_id, label, confidence, now),
            )
            if cur.rowcount:
                propagated += 1

    conn.commit()
    return propagated