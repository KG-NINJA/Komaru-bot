import csv
  import datetime as dt
  import os
  import random
  import sys
  from email.utils import parsedate_to_datetime
  from pathlib import Path
  from typing import Iterable, Iterator
  from urllib.parse import quote_plus
  from xml.etree import ElementTree

  import requests
  from requests import Response, Session
  from requests.adapters import HTTPAdapter
  from urllib3.util.retry import Retry

  # Twitter検索クエリ。環境変数KOMARU_TAGで上書きできる。
  TAG = os.getenv("KOMARU_TAG", "こまる相談")
  # 最大取得件数。必要に応じて調整可能にする。
  LIMIT = int(os.getenv("KOMARU_LIMIT", "100"))
  # 利用するNitterインスタンス群。カンマ区切り指定が無い場合は既定リストを使う。
  DEFAULT_NITTER_BASES = [
      "https://nitter.poast.org",
      "https://nitter.privacydev.net",
      "https://nitter.net",
      "https://nitter.cz",
      "https://nitter.fdn.fr",
      "https://nitter.weiler.rocks",
  ]
  # Farsideなどのプロキシ経由も候補として扱う。
  DEFAULT_PROXY_BASES = [
      "https://farside.link/nitter",
  ]

  # オフライン時に利用するサンプルRSS。存在しない場合は組み込みデータで補う。
  OFFLINE_FEED_PATH = Path(os.getenv("KOMARU_OFFLINE_FEED", "specs/sample_feed.xml"))

  # RSS取得時に利用する共通のHTTPヘッダー。
  HEADERS = {
      "User-Agent": "Mozilla/5.0 (compatible; KomaruBot/1.0; +https://github.com)",
      "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
  }

  # requestsセッションを1つだけ確保し、リトライ設定を共有する。
  SESSION: Session | None = None


  def session() -> Session:
      """requestsセッションを遅延初期化する。"""

      global SESSION  # noqa: PLW0603
      if SESSION is None:
          retries = Retry(
              total=int(os.getenv("KOMARU_RETRY_TOTAL", "3")),
              backoff_factor=float(os.getenv("KOMARU_RETRY_BACKOFF", "1.0")),
              status_forcelist=(429, 500, 502, 503, 504),
              allowed_methods=frozenset({"GET"}),
          )
          adapter = HTTPAdapter(max_retries=retries)
          sess = requests.Session()
          sess.headers.update(HEADERS)
          sess.mount("https://", adapter)
          sess.mount("http://", adapter)
          SESSION = sess
      return SESSION


  def resolve_bases() -> list[str]:
      """NitterのベースURL候補を環境変数から構築する。"""

      env_value = os.getenv("KOMARU_NITTER_BASES")
      if env_value:
          bases = [value.strip() for value in env_value.split(",") if value.strip()]
      else:
          # 従来のKOMARU_NITTER_BASEがあれば先頭に配置し、その後ろに既定値をつなげる。
          primary = os.getenv("KOMARU_NITTER_BASE")
          default_candidates = list(dict.fromkeys(DEFAULT_NITTER_BASES + DEFAULT_PROXY_BASES))
          if primary:
              bases = [primary.strip()] + [
                  base for base in default_candidates if base != primary.strip()
              ]
          else:
              bases = default_candidates

      # ランダムに並べ替えて特定インスタンスへの負荷集中を避ける。
      shuffled = bases[:]
      random.shuffle(shuffled)
      return shuffled


  def build_feed_urls(base_url: str, query: str) -> Iterator[str]:
      """フィード取得に使用するURL候補を返す。"""

      encoded_query = quote_plus(query)
      normalized_base = base_url.rstrip("/")
      rss_path = f"/search/rss?f=tweets&q={encoded_query}"

      # 通常アクセスと、403エラー回避用のr.jina.aiを両方試す。
      yield f"{normalized_base}{rss_path}"
      if not normalized_base.startswith("https://r.jina.ai/"):
          yield f"https://r.jina.ai/{normalized_base}{rss_path}"


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

          try:
              parsed_date = parsedate_to_datetime(raw_date)
              date_iso = parsed_date.isoformat()
          except (TypeError, ValueError):
              date_iso = raw_date

          posts.append({"date": date_iso, "text": title, "url": link})

      return posts


  def iter_feed_candidates(tag: str) -> Iterator[str]:
      """検索タグから複数のRSS URLを生成する。"""

      for base_url in resolve_bases():
          for url in build_feed_urls(base_url, tag):
              yield url


  def request_feed(url: str) -> Response:
      """URLからRSSデータを取得する。"""

      resp = session().get(url, timeout=float(os.getenv("KOMARU_TIMEOUT", "30")))
      resp.raise_for_status()
      if "xml" not in resp.headers.get("Content-Type", "") and "</rss>" not in resp.text:
          # HTMLなど不正な内容の場合は例外として扱う。
          raise ValueError(f"Unexpected content type for {url}")
      return resp


  def fetch_posts() -> list[dict[str, str]]:
      """RSS経由で投稿を取得し、投稿リストを返す。"""

      last_error: Exception | None = None
      for url in iter_feed_candidates(TAG):
          print(f"Fetching feed: {url}")
          try:
              response = request_feed(url)
              return parse_feed(response.text)
          except ElementTree.ParseError as parse_error:
              # HTMLなどRSS以外が返った場合は次の候補に切り替える。
              print(f"警告: {url} の解析に失敗しました ({parse_error})")
              last_error = parse_error
          except Exception as exc:  # noqa: BLE001
              # 失敗時はエラーを記録し、次の候補URLで再試行する。
              print(f"警告: {url} の取得に失敗しました ({exc})")
              last_error = exc

      fallback_posts = load_offline_posts()
      if fallback_posts:
          return fallback_posts

      if last_error is not None:
          print(f"フィード取得に失敗しました: {last_error}")
      return []


  def load_offline_posts() -> list[dict[str, str]]:
      """ローカルに置いたサンプルRSSから投稿を読み込む。"""

      if OFFLINE_FEED_PATH.exists():
          try:
              print(f"情報: ネットワーク代替として {OFFLINE_FEED_PATH} を利用します。")
              xml_text = OFFLINE_FEED_PATH.read_text(encoding="utf-8")
              return parse_feed(xml_text)
          except Exception as exc:  # noqa: BLE001
              print(f"警告: オフラインサンプルの解析に失敗しました ({exc})")
              return []

      # ファイルがない場合は組み込みのシードデータを返す。
      print("情報: オフライン用ファイルが見つからなかったため組み込みサンプルを使用します。")
      return [
          {
              "date": dt.datetime(2024, 1, 1, 0, 0, 0).isoformat(),
              "text": "こまる相談のサンプル投稿です。",
              "url": "https://example.com/sample",
          }
      ]


  def save_posts_csv(posts: Iterable[dict[str, str]], output_path: Path) -> None:
      """投稿データをCSVに保存する。"""

      output_path.parent.mkdir(parents=True, exist_ok=True)
      with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
          writer = csv.DictWriter(csv_file, fieldnames=("date", "text", "url"))
          writer.writeheader()
          for post in posts:
              writer.writerow(post)


  def main() -> int:
      """Twitterから投稿を取得してCSVに書き出すメイン処理。"""

      posts = fetch_posts()
      if not posts:
          print("該当する投稿が見つからなかったか、フィードが空でした。")
          return 1

      output_path = Path(os.getenv("KOMARU_OUTPUT", "komaru_posts.csv"))
      save_posts_csv(posts, output_path)

      timestamp = dt.datetime.now().isoformat()
      print(f"{len(posts)} posts saved to {output_path.resolve()} ({timestamp})")
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
