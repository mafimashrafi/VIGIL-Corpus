"""
Offline tests for llm_labeler.py -- no network, no API key needed.
Uses a fake call_fn to verify candidate selection, idempotency, near-dup
skipping, and label propagation, independent of the real Gemma API.
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "vigil_pipeline" / "label"))
from llm_labeler import label_new_comments, fetch_labelable_rows, propagate_labels_to_duplicates

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def make_test_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def insert_raw_and_clean(conn, rid, content_hash, raw_text, is_near_dup=0, dup_of_id=None):
    conn.execute(
        """INSERT INTO raw_comments (id, content_hash, raw_text, source, fetched_at, last_seen_at)
           VALUES (?, ?, ?, 'youtube', '2026-08-29T10:00:00+00:00', '2026-08-29T10:00:00+00:00')""",
        (rid, content_hash, raw_text),
    )
    conn.execute(
        """INSERT INTO clean_comments (raw_comment_id, clean_text, lang_mix, is_near_dup, dup_of_id, cleaned_at)
           VALUES (?, ?, 'bn', ?, ?, '2026-08-29T10:01:00+00:00')""",
        (rid, raw_text, is_near_dup, dup_of_id),
    )


def fake_bully_labeler(comment, api_key):
    return {"labels": ["bully"], "confidence": 0.9}


def fake_multilabel_labeler(comment, api_key):
    return {"labels": ["sexual", "bully"], "confidence": 0.85}


def fake_unparseable_labeler(comment, api_key):
    return {"labels": [], "confidence": 0.0}


def test_fetch_labelable_rows_excludes_near_duplicates():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "স্বাভাবিক কমেন্ট", is_near_dup=0)
    insert_raw_and_clean(conn, 2, "h2", "স্বাভাবিক কমেন্ট ২", is_near_dup=1, dup_of_id=1)
    conn.commit()

    candidates = fetch_labelable_rows(conn)
    ids = [c["raw_comment_id"] for c in candidates]
    assert ids == [1], f"expected only id 1 (non-duplicate), got {ids}"
    print("PASS: near-duplicate comments are excluded from labeling candidates")


def test_label_new_comments_inserts_multilabel_rows():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "তুই একটা মাল")
    conn.commit()

    summary = label_new_comments(conn, api_key="fake", call_fn=fake_multilabel_labeler, rate_limit_sec=0)
    assert summary["labeled"] == 1

    rows = conn.execute("SELECT label FROM labels WHERE raw_comment_id = 1").fetchall()
    labels = sorted(r[0] for r in rows)
    assert labels == ["bully", "sexual"], f"unexpected: {labels}"
    print("PASS: multi-label result creates one row per label")


def test_unparseable_result_inserts_nothing_and_is_retried():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "কিছু একটা কমেন্ট")
    conn.commit()

    summary = label_new_comments(conn, api_key="fake", call_fn=fake_unparseable_labeler, rate_limit_sec=0)
    assert summary["skipped_unparseable"] == 1
    assert summary["labeled"] == 0

    count = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    assert count == 0, "nothing should be inserted for an unparseable result"

    # confirm it's still a candidate on the next run (naturally retried)
    candidates_again = fetch_labelable_rows(conn)
    assert len(candidates_again) == 1
    print("PASS: unparseable LLM output inserts nothing, and the row remains a candidate for retry")


def test_idempotent_rerun_does_not_relabel():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "ভালো একটা কমেন্ট")
    conn.commit()

    first = label_new_comments(conn, api_key="fake", call_fn=fake_bully_labeler, rate_limit_sec=0)
    assert first["labeled"] == 1

    second = label_new_comments(conn, api_key="fake", call_fn=fake_bully_labeler, rate_limit_sec=0)
    assert second["candidates"] == 0, f"expected 0 candidates on re-run, got {second['candidates']}"

    count = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    assert count == 1, f"expected still 1 label row, got {count}"
    print("PASS: re-running does not re-label already-labeled comments")


def test_propagate_labels_to_duplicates():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "who's watching in 2026", is_near_dup=0)
    insert_raw_and_clean(conn, 2, "h2", "whos watching in 2026", is_near_dup=1, dup_of_id=1)
    conn.commit()

    # label only the canonical comment (id=1) -- id=2 is a near-dup, excluded from LLM candidates
    label_new_comments(conn, api_key="fake", call_fn=fake_bully_labeler, rate_limit_sec=0)

    candidates = fetch_labelable_rows(conn)
    assert candidates == [], "duplicate should never have been sent to the LLM"

    propagated = propagate_labels_to_duplicates(conn)
    assert propagated == 1

    dup_labels = conn.execute("SELECT label FROM labels WHERE raw_comment_id = 2").fetchall()
    assert [r[0] for r in dup_labels] == ["bully"], f"unexpected: {dup_labels}"
    print("PASS: duplicate inherits canonical's label with zero LLM calls spent on it")


def test_propagate_is_idempotent():
    conn = make_test_db()
    insert_raw_and_clean(conn, 1, "h1", "spam text here", is_near_dup=0)
    insert_raw_and_clean(conn, 2, "h2", "spam text here again", is_near_dup=1, dup_of_id=1)
    conn.commit()

    label_new_comments(conn, api_key="fake", call_fn=fake_bully_labeler, rate_limit_sec=0)
    propagate_labels_to_duplicates(conn)
    second_run_propagated = propagate_labels_to_duplicates(conn)

    assert second_run_propagated == 0, "re-running propagation should not create duplicate label rows"
    count = conn.execute("SELECT COUNT(*) FROM labels WHERE raw_comment_id = 2").fetchone()[0]
    assert count == 1
    print("PASS: re-running propagation is idempotent, no duplicate label rows")


if __name__ == "__main__":
    test_fetch_labelable_rows_excludes_near_duplicates()
    test_label_new_comments_inserts_multilabel_rows()
    test_unparseable_result_inserts_nothing_and_is_retried()
    test_idempotent_rerun_does_not_relabel()
    test_propagate_labels_to_duplicates()
    test_propagate_is_idempotent()
    print("\nALL LABELING TESTS PASSED")