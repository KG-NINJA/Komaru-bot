import feedparser, pandas as pd, datetime, os

TAG = os.getenv("KOMARU_TAG", "こまる相談")
rss = f"https://nitter.net/search/rss?f=tweets&q=%23{TAG}"

feed = feedparser.parse(rss)
posts = []

for entry in feed.entries:
    text = entry.title.replace("\n", " ").strip()
    posts.append({
        "date": entry.published,
        "text": text,
    })

if posts:
    df = pd.DataFrame(posts)
    df.to_csv("komaru_posts.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df)} posts saved ({datetime.datetime.now().isoformat()})")
else:
    print("No posts found.")
