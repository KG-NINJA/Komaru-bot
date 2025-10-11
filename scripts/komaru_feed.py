import datetime, os, feedparser, pandas as pd
from pathlib import Path

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; KomaruBot/1.0)"

TAG = os.getenv("KOMARU_TAG", "こまる相談")
rss = f"https://nitter.net/search/rss?f=tweets&q={TAG}"

feed = feedparser.parse(rss)
print(f"Fetched {len(feed.entries)} entries from {rss}")
if getattr(feed, "bozo_exception", None):
    print(f"RSS parse warning: {feed.bozo_exception}")

posts = []
for entry in feed.entries:
    text = entry.title.replace("\n", " ").strip()
    posts.append({"date": entry.published, "text": text})

output_path = Path("komaru_posts.csv")
df = pd.DataFrame(posts)
df.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"{len(df)} posts saved ({datetime.datetime.now().isoformat()})")
