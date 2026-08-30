import os
import sys
import sqlite3
import yaml
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "vigil_pipeline" / "label"))
from llm_labeler import label_new_comments, propagate_labels_to_duplicates

ROOT = Path(__file__).resolve().parent


def main():
    load_dotenv(ROOT / ".env")
    api_key = os.environ["GEMINI_API_KEY"]

    config = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    rate_limit = config.get("rate_limit_sec", 1.0)

    conn = sqlite3.connect(ROOT / config["db_path"])
    conn.executescript((ROOT / "src" / "vigil_pipeline" / "db" / "schema.sql").read_text())

    print("Labeling new comments...")
    summary = label_new_comments(conn, api_key, rate_limit_sec=rate_limit)
    print(f"  candidates: {summary['candidates']}")
    print(f"  labeled: {summary['labeled']}")
    print(f"  skipped (unparseable, will retry next run): {summary['skipped_unparseable']}")

    print("\nPropagating labels to near-duplicates...")
    propagated = propagate_labels_to_duplicates(conn)
    print(f"  propagated to {propagated} duplicate comment(s), zero extra API cost")

    total_labels = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    print(f"\nlabels table now has {total_labels} total rows.")


if __name__ == "__main__":
    main()