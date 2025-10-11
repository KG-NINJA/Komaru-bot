# 🤖 忍法こまる Tag Collector

## 目的
X(旧Twitter) の `#こまる相談` 投稿を自動収集し、CSVとして記録します。
将来は感情分析・ユーモア生成・アプリ化を予定。

## セットアップ
1. 依存ライブラリをインストールする
   ```bash
   pip install pandas requests
   ```
2. このリポジトリをGitHubにPush
3. `.github/workflows/komaru.yml` が自動実行（毎時 or 手動）
4. `komaru_posts.csv` に投稿内容が保存される

### ローカルでの実行方法
- `python scripts/komaru_feed.py` を実行すると、`komaru_posts.csv` に最新投稿が上書き保存されます。
  - 取得に失敗した場合は非ゼロ終了コードを返し、実データが無い限りファイルは更新されません。
- オプションと環境変数で以下を調整できます。
  - `--request-interval` / `KOMARU_REQUEST_INTERVAL`: 429回避のためのリクエスト間隔（秒）
  - `--attempts-per-base` / `KOMARU_ATTEMPTS_PER_BASE`: 各Nitterベースで試すURL数
  - `KOMARU_TAG`: 収集する検索クエリ（デフォルト: `こまる相談`）
  - `KOMARU_LIMIT`: 取得する最大件数（デフォルト: `100`）
  - `KOMARU_NITTER_BASES`: カンマ区切りで複数指定できるNitterインスタンスURL（例: `https://nitter.net,https://nitter.cz`）
  - `--allow-offline` または `KOMARU_ALLOW_OFFLINE=1`: ネットワーク取得が全滅した場合のみローカルサンプル (`KOMARU_OFFLINE_FEED`, 既定は `specs/sample_feed.xml`) にフォールバックする


## 出力例
| date | text |
|------|------|
| 2025-02-11T03:21:00+00:00 | 在宅ワークでお菓子を食べすぎ #こまる相談 |
| 2025-02-11T02:00:00+00:00 | 寝坊して朝の会議に遅刻した… #こまる相談 |

## 拡張案
- `matplotlib` で投稿数グラフを描画  
- `transformers` で感情分類  
- `gradio` で可視化Webアプリ作成  
