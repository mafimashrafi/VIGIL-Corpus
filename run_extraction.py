
import os
import sqlite3
import yaml
from pathlib import Path
from dotenv import load_dotenv

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from vigil_pipeline.extract.youtube import fetch_comments, upsert_comment

ROOT = Path(__file__).resolve().parent


def main():
    load_dotenv(ROOT / ".env")
    api_key = os.environ["YOUTUBE_API_KEY"]

    config = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    rate_limit = config.get("rate_limit_sec", 1.0)

    db_path = ROOT / config["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "src" / "vigil_pipeline" / "db" / "schema.sql").read_text())

    for channel in config["channels"]:
        category = channel.get("category", "unlabeled")
        for video_id in channel.get("video_ids", []):
            print(f"\n--- Mining video {video_id} (channel category: {category}) ---")
            count = 0
            for text, comment_id in fetch_comments(video_id, api_key, rate_limit):
                upsert_comment(conn, text, comment_id, source="youtube")
                count += 1
            conn.commit()
            print(f"    {count} comments upserted")

    total = conn.execute("SELECT COUNT(*) FROM raw_comments").fetchone()[0]
    print(f"\nDone. raw_comments now has {total} total rows.")


if __name__ == "__main__":
    main()