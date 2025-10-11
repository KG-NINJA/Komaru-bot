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
- `python scripts/komaru_feed.py` を実行すると、`komaru_posts.csv` に最新投稿が追記されます。
- 環境変数で以下を調整できます。
  - `KOMARU_TAG`: 収集する検索クエリ（デフォルト: `こまる相談`）
  - `KOMARU_LIMIT`: 取得する最大件数（デフォルト: `100`）
  - `KOMARU_NITTER_BASE`: 利用するNitterインスタンスURL（デフォルト: `https://nitter.net`）

## 出力例
| date | text |
|------|------|
| 2025-10-11 | 「仕事が多すぎて昼休みがない #こまる相談」 |
| 2025-10-11 | 「AIに愚痴を聞いてほしい #こまる相談」 |

## 拡張案
- `matplotlib` で投稿数グラフを描画  
- `transformers` で感情分類  
- `gradio` で可視化Webアプリ作成  
