# 🤖 忍法こまる Tag Collector

## 目的
X(旧Twitter) の `#こまる相談` 投稿を自動収集し、CSVとして記録します。
将来は感情分析・ユーモア生成・アプリ化を予定。

## セットアップ
1. このリポジトリをGitHubにPush  
2. `.github/workflows/komaru.yml` が自動実行（毎時 or 手動）  
3. `komaru_posts.csv` に投稿内容が保存される  

## 出力例
| date | text |
|------|------|
| 2025-10-11 | 「仕事が多すぎて昼休みがない #こまる相談」 |
| 2025-10-11 | 「AIに愚痴を聞いてほしい #こまる相談」 |

## 拡張案
- `matplotlib` で投稿数グラフを描画  
- `transformers` で感情分類  
- `gradio` で可視化Webアプリ作成  
