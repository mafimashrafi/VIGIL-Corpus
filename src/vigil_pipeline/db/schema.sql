CREATE TABLES raw_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL UNIQUE,
    raw_text TEXT NOT NULL,
    source TEXT NOT NULL,
    source_ref_hash TEXT,
    fetched_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

