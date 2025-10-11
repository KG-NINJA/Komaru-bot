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
# 利用するNitterインスタンス群。カンマ区切り指定が無い場合は既定リストを使う。
DEFAULT_NITTER_BASES = [
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.fdn.fr",
    "https://nitter.pufe.org",
]

# オフライン時に利用するサンプルRSS。存在しない場合はスキップする。
OFFLINE_FEED_PATH = Path(os.getenv("KOMARU_OFFLINE_FEED", "specs/sample_feed.xml"))

# RSS取得時に利用する共通のHTTPヘッダー。
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KomaruBot/1.0; +https://github.com)",
}


def resolve_bases() -> list[str]:
    """NitterのベースURL候補を環境変数から構築する。"""

    # KOMARU_NITTER_BASESが指定されている場合はそれを優先する。
    env_value = os.getenv("KOMARU_NITTER_BASES")
    if env_value:
        return [value.strip() for value in env_value.split(",") if value.strip()]

    # 従来のKOMARU_NITTER_BASEがあれば先頭に配置し、その後ろに既定値をつなげる。
    primary = os.getenv("KOMARU_NITTER_BASE")
    if primary:
        return [primary.strip()] + [base for base in DEFAULT_NITTER_BASES if base != primary.strip()]

    return DEFAULT_NITTER_BASES[:]


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

    # 複数ベースURLを順に試し、どれか1つでも成功すれば取得完了とする。
    for base_url in resolve_bases():
        for url in build_feed_urls(base_url, TAG):
            print(f"Fetching feed: {url}")
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                try:
                    return parse_feed(response.text)
                except ElementTree.ParseError as parse_error:
                    # HTMLなどRSS以外が返った場合は次の候補に切り替える。
                    print(f"警告: {url} の解析に失敗しました ({parse_error})")
                    last_error = parse_error
            except Exception as exc:  # noqa: BLE001
                # 失敗時はエラーを記録し、次の候補URLで再試行する。
                print(f"警告: {url} の取得に失敗しました ({exc})")
                last_error = exc

    # オフライン環境などでネットワーク取得が不可能な場合はローカルのサンプルにフォールバックする。
    fallback_posts = load_offline_posts()
    if fallback_posts:
        return fallback_posts

    # すべて失敗した場合は状況を通知し、空リストを返す。
    if last_error is not None:
        print(f"フィード取得に失敗しました: {last_error}")

    return []


def load_offline_posts() -> list[dict[str, str]]:
    """ローカルに置いたサンプルRSSから投稿を読み込む。"""

    if not OFFLINE_FEED_PATH.exists():
        print(f"警告: オフライン用サンプル {OFFLINE_FEED_PATH} が見つかりませんでした。")
        return []

    try:
        print(f"情報: ネットワーク代替として {OFFLINE_FEED_PATH} を利用します。")
        xml_text = OFFLINE_FEED_PATH.read_text(encoding="utf-8")
        return parse_feed(xml_text)
    except Exception as exc:  # noqa: BLE001
        print(f"警告: オフラインサンプルの解析に失敗しました ({exc})")
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
