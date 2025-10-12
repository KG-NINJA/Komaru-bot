import os, sys, feedparser
from pathlib import Path
from datetime import datetime

TAG = os.getenv("KOMARU_TAG", "こまる相談")
LIMIT = int(os.getenv("KOMARU_LIMIT", "20"))
RSS_URL = "https://news.google.com/rss/search?q=悩み+OR+困った+OR+相談&hl=ja&gl=JP&ceid=JP:ja"
OUT_PATH = Path(__file__).resolve().parent.parent / "specs/komaru_feed.txt"

def fetch_feed(url: str, limit: int = 20):
    feed = feedparser.parse(url)
    if not feed.entries:
        print("⚠️ フィードを取得できませんでした。ローカル出力のみ。")
        return []
    return feed.entries[:limit]

def save_feed(entries):
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"=== {TAG} ニュースフィード ({datetime.now():%Y-%m-%d %H:%M}) ===\n\n")
        for e in entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            f.write(f"- {title}\n  {link}\n\n")
    print(f"✅ {len(entries)}件を {OUT_PATH} に保存しました。")

def main():
    entries = fetch_feed(RSS_URL, LIMIT)
    save_feed(entries)

if __name__ == "__main__":
    main()
