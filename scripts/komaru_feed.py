import argparse
import datetime
import importlib.machinery
import importlib.util
import os
import random
import sys
import time
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
    "https://nitter.pl",
    "https://nitter.moomoo.me",
]

# オフライン時に利用するサンプルRSS。存在しない場合はスキップする。
OFFLINE_FEED_PATH = Path(os.getenv("KOMARU_OFFLINE_FEED", "specs/sample_feed.xml"))

# RSS取得時に利用する共通のHTTPヘッダー。
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KomaruBot/1.0; +https://github.com)",
}

# 429対策として試行間隔を秒単位で設定する（環境変数で上書き可能）。
REQUEST_INTERVAL = float(os.getenv("KOMARU_REQUEST_INTERVAL", "2.0"))
# ベースURLごとの最大試行回数。リストが多い場合の全滅抑止に利用する。
MAX_ATTEMPTS_PER_BASE = int(os.getenv("KOMARU_ATTEMPTS_PER_BASE", "3"))


def resolve_bases() -> list[str]:
    """NitterのベースURL候補を環境変数から構築する。"""

    # KOMARU_NITTER_BASESが指定されている場合はそれを優先する。
    env_value = os.getenv("KOMARU_NITTER_BASES")
    if env_value:
        bases = [value.strip() for value in env_value.split(",") if value.strip()]
        # 入力が全て無効だった場合は既定値にフォールバック。
        return bases or DEFAULT_NITTER_BASES[:]

    # 従来のKOMARU_NITTER_BASEがあれば先頭に配置し、その後ろに既定値をつなげる。
    primary = os.getenv("KOMARU_NITTER_BASE")
    if primary:
        filtered_defaults = [base for base in DEFAULT_NITTER_BASES if base != primary.strip()]
        return [primary.strip(), *filtered_defaults]

    return DEFAULT_NITTER_BASES[:]


def truthy_env(name: str, default: bool = False) -> bool:
    """真偽値を扱う環境変数のヘルパー。"""

    # 真偽値文字列を受け取り、既定値を尊重しながら解釈する。
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


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


def fetch_with_nitter(
    *,
    request_interval: float = REQUEST_INTERVAL,
    attempts_per_base: int = MAX_ATTEMPTS_PER_BASE,
    session: requests.Session | None = None,
) -> list[dict[str, str]]:
    """RSS経由で投稿を取得し、投稿リストを返す。"""

    # リトライ時に利用するHTTPセッションを準備する。
    http = session or requests.Session()
    http.headers.update(HEADERS)

    last_error: Exception | None = None
    first_attempt = True

    # 複数ベースURLをランダムシャッフルし、どれか1つでも成功すれば取得完了とする。
    bases = resolve_bases()
    random.shuffle(bases)

    for base_url in bases:
        candidates = build_feed_urls(base_url, TAG)

        # 同一URL重複を排除しつつ、指定回数だけ試行する。
        unique_candidates: list[str] = []
        for candidate in candidates:
            if candidate not in unique_candidates:
                unique_candidates.append(candidate)

        limited_candidates = unique_candidates[: max(1, attempts_per_base)]

        for url in limited_candidates:
            # 429対策のウェイト。初回以外のみ実行する。
            if not first_attempt and request_interval > 0:
                time.sleep(request_interval)

            first_attempt = False
            print(f"Fetching feed: {url}")

            try:
                response = http.get(url, timeout=30)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                # 取得段階で失敗した場合は記録し、次候補へ移動。
                print(f"警告: {url} の取得に失敗しました ({exc})")
                last_error = exc
                continue

            try:
                return parse_feed(response.text)
            except ElementTree.ParseError as parse_error:
                # HTMLなどRSS以外が返った場合は次の候補に切り替える。
                print(f"警告: {url} の解析に失敗しました ({parse_error})")
                last_error = parse_error

    # すべて失敗した場合は状況を通知し、空リストを返す。
    if last_error is not None:
        print(f"フィード取得に失敗しました: {last_error}")

    return []


# X API検索エンドポイント（環境変数で上書き可能）。
X_API_SEARCH_URL = os.getenv(
    "KOMARU_TWITTER_SEARCH_URL",
    "https://api.x.com/2/tweets/search/recent",
)


def get_bearer_token() -> str | None:
    """X API用Bearerトークンを環境変数から取得する。"""

    # APIキーは秘密情報なので、存在しない場合は即座にNoneを返す。
    token = os.getenv("KOMARU_TWITTER_BEARER_TOKEN")
    if token:
        return token.strip()

    # レガシーなTWITTER_BEARER_TOKENにも対応して互換性を保つ。
    fallback = os.getenv("TWITTER_BEARER_TOKEN")
    return fallback.strip() if fallback else None


def fetch_with_x_api(
    *,
    limit: int = LIMIT,
    session: requests.Session | None = None,
) -> list[dict[str, str]]:
    """公式X APIのRecent Searchで投稿を取得する。"""

    token = get_bearer_token()
    if not token:
        print("情報: KOMARU_TWITTER_BEARER_TOKENが未設定のためX APIをスキップします。")
        return []

    http = session or requests.Session()
    http.headers.update(HEADERS)
    http.headers["Authorization"] = f"Bearer {token}"

    # X APIの1回のmax_resultsは100件なので、ページングで必要件数を満たす。
    remaining = max(0, limit)
    params = {
        "query": TAG,
        "tweet.fields": "created_at",  # 日付をISO形式で取得する。
        "expansions": "author_id",  # APIコールの整合性維持のため指定。
        "max_results": min(max(remaining, 10), 100),
    }

    next_token: str | None = None
    posts: list[dict[str, str]] = []

    while remaining > 0:
        if next_token:
            params["next_token"] = next_token
        elif "next_token" in params:
            del params["next_token"]

        print(f"Fetching X API feed: {X_API_SEARCH_URL}")

        try:
            response = http.get(X_API_SEARCH_URL, params=params, timeout=30)
        except Exception as exc:  # noqa: BLE001
            print(f"警告: X APIへのリクエストに失敗しました ({exc})")
            return []

        if response.status_code == 401:
            print("警告: X APIの認証に失敗しました (401 Unauthorized)。")
            return []
        if response.status_code == 429:
            print("警告: X APIのレートリミットに到達しました (429)。")
            return []
        if response.status_code >= 400:
            print(f"警告: X APIからエラー応答を受信しました ({response.status_code})")
            return []

        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            print(f"警告: X APIのJSON解析に失敗しました ({exc})")
            return []

        data = payload.get("data", [])
        if not isinstance(data, list):
            print("警告: X APIの応答にdata配列が含まれていません。")
            return []

        for item in data:
            if remaining <= 0:
                break

            # created_atをISO形式でそのまま利用する。
            created_at = item.get("created_at", "")
            posts.append(
                {
                    "date": created_at,
                    "text": str(item.get("text", "")).replace("\n", " ").strip(),
                    "url": f"https://x.com/i/web/status/{item.get('id', '')}",
                }
            )
            remaining -= 1

        next_token = payload.get("meta", {}).get("next_token")
        if not next_token:
            break

        # 次ページのmax_resultsは残数に応じて更新する。
        params["max_results"] = min(max(remaining, 10), 100)

    if not posts:
        print("警告: X APIで投稿が取得できませんでした。")

    return posts


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


def fetch_with_snscrape(limit: int = LIMIT) -> list[dict[str, str]]:
    """snscrapeを用いてTwitter検索を行い、投稿データを生成する。"""

    # Python 3.12以降ではsnscrape内部のレガシーAPIが削除されているため、互換レイヤーを注入する。
    if not hasattr(importlib.machinery.FileFinder, "find_module"):
        print("情報: snscrape互換パッチを適用します (FileFinder.find_moduleの復元)。")

        def _legacy_find_module(self, fullname, path=None):  # noqa: ANN001,D401
            """find_specを利用して旧来のfind_moduleをエミュレートする。"""

            spec = self.find_spec(fullname, path)
            if spec is None or spec.loader is None:
                return None

            loader = spec.loader
            if hasattr(loader, "load_module"):
                return loader

            class _LoaderWrapper:
                """exec_moduleしか持たないローダーをload_module互換に包む。"""

                def __init__(self, spec_obj):
                    self._spec = spec_obj

                def load_module(self, fullname):  # noqa: ANN001
                    module = importlib.util.module_from_spec(self._spec)
                    if hasattr(self._spec.loader, "exec_module"):
                        self._spec.loader.exec_module(module)  # type: ignore[attr-defined]
                    else:
                        raise ImportError("loaderにexec_moduleが存在しません")
                    sys.modules[fullname] = module
                    return module

            return _LoaderWrapper(spec)

        importlib.machinery.FileFinder.find_module = _legacy_find_module  # type: ignore[attr-defined]

    try:
        # 動的インポートで依存関係が無い環境でも即エラーにならないようにする。
        from snscrape.modules.twitter import TwitterSearchScraper  # type: ignore[import-not-found]
    except ImportError as exc:
        print(f"警告: snscrapeのインポートに失敗しました ({exc})")
        return []

    print("情報: Nitterの代替としてsnscrapeによる直接スクレイピングを試行します。")

    try:
        scraper = TwitterSearchScraper(TAG)
    except Exception as exc:  # noqa: BLE001
        print(f"警告: snscrapeの初期化に失敗しました ({exc})")
        return []

    posts: list[dict[str, str]] = []

    try:
        for index, tweet in enumerate(scraper.get_items()):
            if index >= limit:
                break

            # snscrapeが返すtweetオブジェクトから必要情報を抽出する。
            date_iso = ""
            if getattr(tweet, "date", None) is not None:
                try:
                    date_iso = tweet.date.isoformat()
                except Exception:  # noqa: BLE001
                    date_iso = str(tweet.date)

            content = getattr(tweet, "content", "")
            url = getattr(tweet, "url", "")

            posts.append(
                {
                    "date": date_iso,
                    "text": str(content).replace("\n", " ").strip(),
                    "url": str(url),
                }
            )
    except Exception as exc:  # noqa: BLE001
        print(f"警告: snscrapeによる取得中にエラーが発生しました ({exc})")
        return []

    return posts


def main():
    """Twitterから投稿を取得してCSVに書き出すメイン処理。"""

    parser = argparse.ArgumentParser(description="こまる相談のTwitter検索結果を取得する。")
    parser.add_argument(
        "--allow-offline",
        dest="allow_offline",
        action="store_true",
        default=None,
        help="取得に失敗した際にローカルサンプルへフォールバックする",
    )
    parser.add_argument(
        "--disallow-offline",
        dest="allow_offline",
        action="store_false",
        default=None,
        help="オフラインフォールバックを明示的に無効化する",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=None,
        help="連続リクエストのウェイト秒数（429対策）",
    )
    parser.add_argument(
        "--attempts-per-base",
        type=int,
        default=None,
        help="各ベースURLに対して試す候補数",
    )
    parser.add_argument(
        "--disable-snscrape",
        action="store_true",
        help="Nitter失敗時のsnscrapeフォールバックを無効化する",
    )
    parser.add_argument(
        "--enable-snscrape",
        action="store_true",
        help="snscrapeフォールバックを強制的に有効化する",
    )
    parser.add_argument(
        "--disable-x-api",
        action="store_true",
        help="公式X API経由での取得を無効化する",
    )
    parser.add_argument(
        "--enable-x-api",
        action="store_true",
        help="公式X API経由での取得を強制的に有効化する",
    )

    args = parser.parse_args()

    allow_offline = (
        args.allow_offline
        if args.allow_offline is not None
        else truthy_env("KOMARU_ALLOW_OFFLINE", default=False)
    )
    request_interval = (
        args.request_interval if args.request_interval is not None else REQUEST_INTERVAL
    )
    attempts_per_base = (
        args.attempts_per_base if args.attempts_per_base is not None else MAX_ATTEMPTS_PER_BASE
    )
    enable_snscrape = truthy_env("KOMARU_ENABLE_SNSCRAPE", default=True)
    enable_x_api = truthy_env(
        "KOMARU_ENABLE_X_API",
        default=get_bearer_token() is not None,
    )

    if args.disable_snscrape:
        enable_snscrape = False
    if args.enable_snscrape:
        enable_snscrape = True
    if args.disable_x_api:
        enable_x_api = False
    if args.enable_x_api:
        enable_x_api = True

    posts: list[dict[str, str]] = []

    if enable_x_api:
        posts = fetch_with_x_api(limit=LIMIT)

    if not posts:
        posts = fetch_with_nitter(
            request_interval=request_interval,
            attempts_per_base=attempts_per_base,
        )

    if not posts and enable_snscrape:
        posts = fetch_with_snscrape(limit=LIMIT)

    if not posts and allow_offline:
        print("情報: オフラインフォールバックを許可しているため、サンプルデータへ切り替えます。")
        posts = load_offline_posts()

    if not posts:
        print("エラー: フィード取得に成功せず、書き出すデータがありません。")
        raise SystemExit(1)

    df = pd.DataFrame(posts)

    output_path = Path("komaru_posts.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    timestamp = datetime.datetime.now().isoformat()
    print(f"{len(df)} posts saved to {output_path.resolve()} ({timestamp})")


if __name__ == "__main__":
    main()
