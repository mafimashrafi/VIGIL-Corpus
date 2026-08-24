"""
Usage:
    python test_fetch.py <VIDEO_ID>

Example:
    python test_fetch.py dQw4w9WgXcQ
"""
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()  

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def fetch_comments(video_id, api_key, max_comments=50):
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": 100,
        "textFormat": "plainText",
        "key": api_key,
    }
    fetched = 0

    while True:
        resp = requests.get(API_URL, params=params, timeout=10)

        if resp.status_code == 403:
            print("ERROR 403 — check that YouTube Data API v3 is enabled and your key is correct.")
            print(resp.json())
            return
        if resp.status_code == 429:
            print("Rate limited, waiting 5s...")
            time.sleep(5)
            continue
        resp.raise_for_status()

        data = resp.json()
        items = data.get("items", [])

        for item in items:
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = snippet["textOriginal"]
            author = snippet.get("authorDisplayName", "unknown")  # for eyeballing only, never store this
            print(f"[{fetched + 1}] {text}")
            fetched += 1
            if fetched >= max_comments:
                return

        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
        time.sleep(1)

    print(f"\nDone. Fetched {fetched} comments total.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_fetch.py <VIDEO_ID>")
        sys.exit(1)

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY not found. Check your .env file is in this folder.")
        sys.exit(1)

    fetch_comments(sys.argv[1], api_key)