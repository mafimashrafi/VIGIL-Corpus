"""
End-to-end test for run_cleaning.py -- no network needed.
Builds a temp DB with realistic raw_comments rows, runs the full clean
pipeline, and checks clean_comments came out correctly.
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_cleaning import clean_new_comments, fetch_unclean_rows

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "vigil_pipeline" / "db" / "schema.sql"


def make_test_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def insert_raw(conn, content_hash, text, source, fetched_at):
    conn.execute(
        """INSERT INTO raw_comments (content_hash, raw_text, source, source_ref_hash, fetched_at, last_seen_at)
           VALUES (?, ?, ?, 'dummy_hash', ?, ?)""",
        (content_hash, text, source, fetched_at, fetched_at),
    )


def test_full_pipeline_end_to_end():
    conn = make_test_db()
    insert_raw(conn, "h1", "ভাই গানটা 🔥🔥 অসাধারণ হইছে", "youtube", "2026-08-29T10:00:00+00:00")
    insert_raw(conn, "h2", "tui to ekta boka, kisu janis na", "youtube", "2026-08-29T10:05:00+00:00")
    insert_raw(conn, "h3", "who's watching in 2026 like this comment", "youtube", "2026-08-29T10:10:00+00:00")
    insert_raw(conn, "h4", "whos watching in 2026 like this comment", "youtube", "2026-08-29T10:11:00+00:00")
    insert_raw(conn, "h5", "This is a great video, thanks for sharing", "youtube", "2026-08-29T10:15:00+00:00")
    conn.commit()

    count = clean_new_comments(conn)
    assert count == 5, f"expected 5 processed, got {count}"
    print("PASS: all 5 raw rows processed in one run")

    rows = conn.execute(
        "SELECT raw_comment_id, clean_text, lang_mix, emoji_flags, is_near_dup, dup_of_id FROM clean_comments ORDER BY raw_comment_id"
    ).fetchall()
    assert len(rows) == 5
    print("PASS: clean_comments has exactly 5 rows")

    by_id = {r[0]: r for r in rows}

    _, clean_text, lang_mix, emoji_flags, _, _ = by_id[1]
    assert "🔥" not in clean_text, "emoji should be stripped from clean_text"
    assert lang_mix == "bn"
    assert emoji_flags is not None and "🔥" in emoji_flags
    print("PASS: Bangla comment with emoji -> emoji stripped from clean_text, captured in emoji_flags, lang_mix='bn'")

    _, _, lang_mix2, _, _, _ = by_id[2]
    assert lang_mix2 == "banglish", f"expected banglish, got {lang_mix2}"
    print("PASS: Banglish comment correctly detected")

    _, _, _, _, is_dup3, dup_of3 = by_id[3]
    _, _, _, _, is_dup4, dup_of4 = by_id[4]
    assert is_dup3 == 0, "first spam comment should be canonical, not flagged"
    assert is_dup4 == 1 and dup_of4 == 3, f"second spam comment should point to id 3, got is_dup={is_dup4}, dup_of={dup_of4}"
    print("PASS: near-duplicate spam pair correctly linked (first canonical, second flagged)")

    _, _, lang_mix5, _, is_dup5, _ = by_id[5]
    assert lang_mix5 == "en"
    assert is_dup5 == 0
    print("PASS: distinct English comment not flagged as duplicate")


def test_idempotent_rerun_does_not_reprocess():
    conn = make_test_db()
    insert_raw(conn, "h1", "ভাই গানটা অসাধারণ", "youtube", "2026-08-29T10:00:00+00:00")
    conn.commit()

    first_count = clean_new_comments(conn)
    assert first_count == 1

    second_count = clean_new_comments(conn)
    assert second_count == 0, f"expected 0 on re-run (nothing new), got {second_count}"

    total = conn.execute("SELECT COUNT(*) FROM clean_comments").fetchone()[0]
    assert total == 1, f"expected still 1 row total, got {total}"
    print("PASS: re-running with no new raw rows processes 0 rows and creates no duplicates")


def test_only_new_rows_processed_on_second_run():
    conn = make_test_db()
    insert_raw(conn, "h1", "প্রথম কমেন্ট", "youtube", "2026-08-29T10:00:00+00:00")
    conn.commit()
    clean_new_comments(conn)

    insert_raw(conn, "h2", "দ্বিতীয় কমেন্ট", "youtube", "2026-08-29T11:00:00+00:00")
    conn.commit()

    second_run_count = clean_new_comments(conn)
    assert second_run_count == 1, f"expected exactly 1 new row processed, got {second_run_count}"

    total = conn.execute("SELECT COUNT(*) FROM clean_comments").fetchone()[0]
    assert total == 2
    print("PASS: only the newly added raw row gets processed on the second run, old row untouched")


if __name__ == "__main__":
    test_full_pipeline_end_to_end()
    test_idempotent_rerun_does_not_reprocess()
    test_only_new_rows_processed_on_second_run()
    print("\nALL CLEANING PIPELINE TESTS PASSED")