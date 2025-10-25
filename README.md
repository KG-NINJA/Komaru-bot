# 🤖 忍法こまる Tag Collector

## 概要
GoogleニュースのRSSから「悩み」「困った」などの投稿を収集し、最新のフィードを `specs/komaru_feed.txt` に書き出す自動化プロジェクトです。このテキストは毎週のAutoApp生成ワークフローの入力として利用され、最新の困りごとに対応したサンプルアプリを自動で作成します。

## リポジトリ構成ハイライト
- `scripts/komaru_feed.py`: RSSを取得して `specs/komaru_feed.txt` を更新するPythonスクリプト。
- `scripts/generate_app.py`: YAML仕様からアプリ雛形を生成するCLIツール（OpenAI API利用）。
- `specs/template.yaml`: AutoApp用YAML仕様のテンプレート。
- `apps/latest_app/`: 自動生成された最新アプリの成果物が保存されるディレクトリ。

## セットアップ
1. 依存ライブラリをインストールします。
   ```bash
   pip install -r requirements.txt
   ```
2. OpenAIを使った自動アプリ生成をローカルで試す場合は、`pip install openai pyyaml` を追加インストールし、`OPENAI_API_KEY` を環境変数に設定してください。

## フィード収集スクリプトの使い方
```bash
python scripts/komaru_feed.py
```
- デフォルトでは GoogleニュースRSS から最大20件を取得し、`specs/komaru_feed.txt` を丸ごと更新します。
- 利用可能な環境変数:
  - `KOMARU_TAG`: 見出しに表示するタグ名（デフォルト: `こまる相談`）。
  - `KOMARU_LIMIT`: 取得件数の上限（デフォルト: `20`）。
- フィードが取得できない場合は警告を表示し、空のテンプレートファイルを出力します。

## YAML仕様からのアプリ生成
1. `specs/template.yaml` をコピーし、`id`, `problem_statement`, `features` などを埋めた仕様ファイルを作成します。
2. `auto_generate: true` に設定します。
3. 次のコマンドでアプリを生成します。
   ```bash
   python scripts/generate_app.py <specファイルのパス> --output-dir generated_apps
   ```
   - `generated_apps/<specのid>/` に生成ファイル一式とメタデータが保存されます。
   - `--model` オプションで使用するモデル名を指定できます（デフォルト: `gpt-4o-mini`）。

## GitHub Actions ワークフロー
- `.github/workflows/komaru.yml`
  - 毎時 (`cron: 0 * * * *`) および手動で実行可能。
  - `feedparser` と `pandas` をインストール後、`scripts/komaru_feed.py` を実行し、`specs/komaru_feed.txt` を更新してコミットします。
- `.github/workflows/komaru_autoapp.yml`
  - 毎週月曜 UTC 0時（JST 9時）に実行。
  - フィード取得後、OpenAI Codex Action を使って `apps/latest_app/` にHTMLアプリとREADMEを生成し、GitHub Pagesへデプロイします。

## 既知の成果物
- `specs/komaru_feed.txt`: 最新の困りごと一覧を保持するテキストファイル。
- `apps/latest_app/`: 最新のAutoApp成果物。GitHub Pages公開対象にもなります。

将来的には感情分析やユーモア生成などの拡張も視野に入れて開発を進める想定です。
