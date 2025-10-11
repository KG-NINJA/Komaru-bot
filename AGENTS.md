# AGENTS

本リポジトリは Codex CLI を素早く活用できるよう、拡張しやすい「ブロック指向」のスキャフォールドを提供します。
標準ライブラリのみで動作し、失敗したくてもできない仕組みを備えています。
#KGNINJA

---

## ローカルマシン環境

* プロセッサ Intel(R) Core(TM) i5-10310U CPU @ 1.70GHz (2.21 GHz)
* 実装 RAM 16.0 GB (15.7 GB 使用可能)
* Windows 11

---

## Principles (設計原則)

* **安全性**: dry-run 推奨、未知プラグインは警告のみで安全にスキップ
* **教育性**: scaffold / describe / doctor で自然に学べる
* **拡張性**: registry と @register_block で容易に追加・削除可能
* **貢献性**: 将来的なOSS公開を見据え、誰でも参加しやすい設計
* **長期最適化**: 単発スコアよりも、時間割引した累積報酬/ユーティリティを最大化
* **代理指標の健全性**: 人間の理念は直接数値化しにくいため、代理指標と対指標を組み合わせる
* **可観測性**: 性能・安定性・探索率をログ化し、データ欠損時は安全側にフォールバック

---

## Quick Use

* 自動選択: `python -m kgninja_agent`

* 実行: `python -m kgninja_agent run --profile power --plugin research --text "調査テーマ"`

* 一覧: `python -m kgninja_agent list`

* 詳細: `python -m kgninja_agent describe --plugin research`

* 環境診断: `python -m kgninja_agent doctor`

* 雛形生成: `python -m kgninja_agent scaffold plugin --dry-run`

---

## Structure

* `cli.py`: CLI 実装（run/list/describe/doctor/scaffold）
* `core.py`: Runner・registry・安全実行ラッパ
* `config.py`: プロファイル設定（fast/power）
* `types.py`: BlockSpec, BlockContext, ProfileConfig, BlockResult
* `hooks.py`: モデルフック（mock/echo/noop 切替）
* `plugins/`: ブロック群
  * `base.py`: 抽象・登録デコレータ
  * `research_power.py`: リサーチ用 (power)
  * `code_fast.py`: コード修正用 (fast)

---

## Plugin Rules

1. 新規プラグインは `plugins/` に配置
2. `@register_block` で登録
3. `get_block()` で BlockSpec を返す
4. `run()` に処理を実装
5. dry-run で生成・検証してから利用

---

## Reward Design（報酬設計）

* 多目的合成: `R = w1*R_task + w2*R_ux + w3*R_safety - w4*C_compute - w5*C_latency`
* ペナルティ例: ループ、重複実行、プロンプト逸脱、リソース過消費、未根拠断定
* 報酬ハッキング対策: 検証分離・ランダム監査・指標ごとの閾値管理

---

## Exploration–Exploitation（探索と活用）

* ε-greedy/Thompson/UCB を時間減衰させ安定期に探索を抑制
* 危険領域はサンドボックスでのみ探索
* 不確実性の高いタスクほど探索比率を上げる
* 自己改善できるログをAGENT.mdに自動追記していく

---

## Anti-Regress（局所解・劣化防止）

* モデル番兵: 性能が下落した場合は自動ロールバック
* メトリクス分解や反事例テストで退行検知
* 既知良好ポリシーへの KL 正則化で逸脱を制限

---

## Proxy Misalignment（代理指標の落とし穴）

* 人間理念は抽象度が高く、代理指標の並列管理が必要
* 外生ショックや仕様変更に対する頑健性試験を実施
* 満足化アプローチで下限保証

---

## Evaluation（評価）

* オフライン: 合成ベンチ、反事例、ストレステスト
* オンライン: A/B テスト、フェーズド配信
* 長期指標: セッション継続率、反復成功率、リワーク率

---

## Guardrails（ガードレール）

* 計算/時間予算超過で打ち切り＋要約出力
* ループ検知、矛盾自己評価、外部ルール抵触で `Halt`
* 権限分離: 読み取り・書き込み・ネットワークをトークン管理

---

## Governance（監査・ガバナンス）

* メトリクス閾値変更はPR＋監査ログ必須
* 重要意思決定には入力・計画・評価を保存
* 緊急停止用ランブックと当番連絡先を明記

##使えば使うほど成長する

* そのセッションで失敗したことを教訓に次回は失敗しないようにする
* 技術を使えば使うほどそれをさらに効率よく使えるようする
* 毎回このAGENTS.mdに自己改善計画を追記していく
　
