import os, time, hashlib, sqlite3, requests
from datetime import datetime, timezone

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

def fetch_comments(video_id, api_key, rate_limit_sec=1.0):
    params = {"part": "snippet", "videoId": video_id, "maxResults": 100,
            "textFormat": "plainText", "key": api_key}
    while True:
        resp = requests.get(API_URL, params=params, timeout=10)
        if resp.status_code == 429:
            time.sleep(5); continue
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            yield top["textOriginal"], item["snippet"]["topLevelComment"]["id"]
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
        time.sleep(rate_limit_sec)

def upsert_comment(conn, text, external_id, source):
    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    ref_hash = hashlib.sha256(external_id.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO raw_comments (content_hash, raw_text, source, source_ref_hash, fetched_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(content_hash) DO UPDATE SET last_seen_at=excluded.last_seen_at
    """, (content_hash, text, source, ref_hash, now, now))

if __name__ == "__main__":
    api_key = os.environ["YOUTUBE_API_KEY"]
    conn = sqlite3.connect("data/vigil.db")
    for text, cid in fetch_comments("VIDEO_ID_HERE", api_key):
        upsert_comment(conn, text, cid, source="youtube")
    conn.commit()