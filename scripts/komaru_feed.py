import os
import sys
import feedparser
from pathlib import Path
from datetime import datetime

# ========= 設定 =========
TAG = os.getenv("KOMARU_TAG", "こまる相談")
LIMIT = int(os.getenv("KOMARU_LIMIT", "20"))
RSS_URL = "https://news.google.com/rss/search?q=悩み+OR+困った+OR+相談&hl=ja&gl=JP&ceid=JP:ja"
OUT_PATH = Path("specs/komaru_feed.txt")

# ========= 処理関数 =========
def fetch_feed(url: str, limit: int = 20):
    """RSSフィードを取得して整形"""
    feed = feedparser.parse(url)
    if not feed.entries:
        print("⚠️ フィードを取得できませんでした。URLまたはネットワークを確認。")
        sys.exit(1)
    return feed.entries[:limit]

def save_feed(entries):
    """タイトルとリンクを保存"""
    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"=== {TAG} ニュースフィード ({datetime.now():%Y-%m-%d %H:%M}) ===\n\n")
        for e in entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            f.write(f"- {title}\n  {link}\n\n")
    print(f"✅ {len(entries)}件を {OUT_PATH} に保存しました。")

# ========= エントリーポイント =========
def main():
    entries = fetch_feed(RSS_URL, LIMIT)
    save_feed(entries)

if __name__ == "__main__":
    main()
