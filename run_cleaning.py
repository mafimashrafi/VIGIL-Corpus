import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from vigil_pipeline.clean.normalize import normalize_text
from vigil_pipeline.clean.emoji import process_emoji, emoji_flags_json
from vigil_pipeline.clean.lang_detect import detect_lang_mix
from vigil_pipeline.clean.dedup import find_near_duplicates

ROOT = Path(__file__).resolve().parent


def fetch_unclean_rows(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        """
        SELECT r.id, r.raw_text, r.source, r.fetched_at
        FROM raw_comments r
        LEFT JOIN clean_comments c ON c.raw_comment_id = r.id
        WHERE c.raw_comment_id IS NULL
        ORDER BY r.fetched_at
        """
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def clean_new_comments(conn: sqlite3.Connection) -> int:
    rows = fetch_unclean_rows(conn)
    if not rows:
        return 0

    processed = []
    for row in rows:
        normalized = normalize_text(row["raw_text"])
        emoji_free_text, emojis, _threat_signal = process_emoji(normalized)
        lang_mix = detect_lang_mix(emoji_free_text)
        processed.append({
            "raw_comment_id": row["id"],
            "source": row["source"],
            "date_bucket": row["fetched_at"][:10],  # YYYY-MM-DD, for dedup grouping
            "clean_text": emoji_free_text,
            "lang_mix": lang_mix,
            "emoji_flags": emoji_flags_json(emojis),
        })

    groups = defaultdict(list)
    for item in processed:
        key = (item["source"], item["date_bucket"])
        groups[key].append({"id": item["raw_comment_id"], "text": item["clean_text"]})

    dup_map = {}  
    for group_records in groups.values():
        dup_map.update(find_near_duplicates(group_records))

    now = datetime.now(timezone.utc).isoformat()
    for item in processed:
        rid = item["raw_comment_id"]
        is_dup = rid in dup_map
        conn.execute(
            """
            INSERT INTO clean_comments
                (raw_comment_id, clean_text, lang_mix, emoji_flags, is_near_dup, dup_of_id, cleaned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                item["clean_text"],
                item["lang_mix"],
                item["emoji_flags"],
                1 if is_dup else 0,
                dup_map.get(rid),
                now,
            ),
        )
    conn.commit()
    return len(processed)


if __name__ == "__main__":
    import yaml

    config = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    db_path = ROOT / config["db_path"]
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "db" / "schema.sql").read_text())

    count = clean_new_comments(conn)
    total_clean = conn.execute("SELECT COUNT(*) FROM clean_comments").fetchone()[0]
    total_dup = conn.execute("SELECT COUNT(*) FROM clean_comments WHERE is_near_dup = 1").fetchone()[0]

    print(f"Cleaned {count} new row(s).")
    print(f"clean_comments now has {total_clean} total rows ({total_dup} flagged as near-duplicates).")