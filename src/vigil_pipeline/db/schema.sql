CREATE TABLE IF NOT EXISTS raw_comments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL UNIQUE,
    raw_text        TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_ref_hash TEXT,
    fetched_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clean_comments (
    raw_comment_id  INTEGER PRIMARY KEY REFERENCES raw_comments(id),
    clean_text      TEXT NOT NULL,
    lang_mix        TEXT NOT NULL CHECK(lang_mix IN ('bn','en','bn_en_mixed','banglish')),
    emoji_flags     TEXT,
    is_near_dup     INTEGER NOT NULL DEFAULT 0,
    dup_of_id       INTEGER REFERENCES raw_comments(id),
    cleaned_at      TEXT NOT NULL
);