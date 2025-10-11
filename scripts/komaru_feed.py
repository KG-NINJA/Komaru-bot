import datetime
import os
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from xml.etree import ElementTree

import pandas as pd
import requests

# Twitter検索クエリ。環境変数KOMARU_TAGで上書きできる。
TAG = os.getenv("KOMARU_TAG", "こまる相談")
# 最大取得件数。必要に応じて調整可能にする。
LIMIT = int(os.getenv("KOMARU_LIMIT", "100"))
# 利用するNitterインスタンス。障害時に切り替えられるようにする。
NITTER_BASE = os.getenv("KOMARU_NITTER_BASE", "https://nitter.net")

# RSS取得時に利用する共通のHTTPヘッダー。
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KomaruBot/1.0; +https://github.com)",
}


def build_feed_urls(base_url: str, query: str) -> list[str]:
    """フィード取得に使用するURL候補を返す。"""

    # 検索クエリをURLエンコードしてパスを構築する。
    encoded_query = quote_plus(query)
    normalized_base = base_url.rstrip("/")
    rss_path = f"/search/rss?f=tweets&q={encoded_query}"

    urls = [f"{normalized_base}{rss_path}"]

    # 403エラー対策としてr.jina.aiプロキシ経由も候補に加える。
    if not normalized_base.startswith("https://r.jina.ai/"):
        urls.append(f"https://r.jina.ai/{normalized_base}{rss_path}")

    return urls


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    """RSSフィードから投稿情報を抽出する。"""

    posts: list[dict[str, str]] = []
    root = ElementTree.fromstring(xml_text)

    for index, item in enumerate(root.findall(".//item")):
        if index >= LIMIT:
            break

        title = (item.findtext("title") or "").replace("\n", " ").strip()
        link = item.findtext("link") or ""
        raw_date = item.findtext("pubDate") or ""

        # RSSの日時文字列をISO形式に変換する。
        try:
            parsed_date = parsedate_to_datetime(raw_date)
            date_iso = parsed_date.isoformat()
        except (TypeError, ValueError):
            date_iso = raw_date

        posts.append({
            "date": date_iso,
            "text": title,
            "url": link,
        })

    return posts


def fetch_posts() -> list[dict[str, str]]:
    """RSS経由で投稿を取得し、投稿リストを返す。"""

    last_error: Exception | None = None

    for url in build_feed_urls(NITTER_BASE, TAG):
        print(f"Fetching feed: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return parse_feed(response.text)
        except Exception as exc:  # noqa: BLE001
            # 失敗時はエラーを記録し、次の候補URLで再試行する。
            print(f"警告: {url} の取得に失敗しました ({exc})")
            last_error = exc

    # すべて失敗した場合は、最後のエラーをまとめて通知する。
    if last_error is not None:
        raise SystemExit(f"フィード取得に失敗しました: {last_error}") from last_error

    return []


def main():
    """Twitterから投稿を取得してCSVに書き出すメイン処理。"""

    posts = fetch_posts()

    if not posts:
        print("該当する投稿が見つからなかったか、フィードが空でした。")
        return

    df = pd.DataFrame(posts)

    output_path = Path("komaru_posts.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    timestamp = datetime.datetime.now().isoformat()
    print(f"{len(df)} posts saved to {output_path.resolve()} ({timestamp})")


if __name__ == "__main__":
    main()
