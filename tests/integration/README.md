# 実機統合テスト（E01 / 方向 A）

このディレクトリは **物理 Windows 環境・USB デバイス・libewf バイナリ** が揃ったうえで実施する統合テストの記録・補助スクリプト用です。CI では自動実行しません。

## 成果物

| ファイル | 説明 |
|----------|------|
| [`test_stdout_parser.py`](test_stdout_parser.py) | 保存した `ewfacquire` / `ewfverify` の stdout を `constants.py` の正規表現で検証（**Week 2 ゲート**） |
| [`ewfacquire_stdout_sample.txt`](ewfacquire_stdout_sample.txt) | ドキュメント上の出力例（パーサー・スモーク用） |
| [`test_reference_hashes.json.example`](test_reference_hashes.json.example) | リファレンスハッシュ記録のテンプレート |
| [`test_environment_template.md`](test_environment_template.md) | テスト PC・USB・ツールバージョンの記録テンプレート |
| [`e01_test_results_TEMPLATE.md`](e01_test_results_TEMPLATE.md) | テストケース別結果の記録テンプレート |
| [`e01_test_results_20260331.md`](e01_test_results_20260331.md) | v2.1.0 実機テスト記録（2026-03-31） |

実結果は `e01_test_results_YYYYMMDD.md` などの名前でコピーして利用してください。

## 実行計画（要約）

NIST CFTT のディスクイメージング観点（ソース読取の正確さ・ハッシュ一致・メタデータ）に沿い、少なくとも次を実施します。

1. **Day 1**: `ewfacquire -V` / `ewfverify -V`、設定画面の接続テスト、リファレンス RAW 取得とハッシュ記録。
2. **Day 2（必須ゲート）**: 実機取得の stdout を保存し、`test_stdout_parser.py` でパターン一致を確認。不一致なら `src/utils/constants.py` の正規表現と `tests/test_e01_writer.py` を修正してから続行。
3. **Day 3–5**: 計画書のカテゴリ A–E、回帰 `pytest`、README / CHANGELOG の更新。

詳細な TC 一覧・スケジュール・リスクはリポジトリ外の計画書または社内 Wiki に従ってください。

## コードベースとの差分メモ（計画書の修正）

- **ハッシュ行**: 実装は `E01_HASH_PATTERN`（アルゴリズム名＋hex を一括）です。計画書の `E01_MD5_PATTERN` / `E01_SHA1_PATTERN` という名前は使用していません。
- **DB カラム**: `e01_ewfacquire_version`（計画書の `e01_tool_version` 相当）。`e01_command_line`, `e01_segment_count`, `e01_compression` など。
- **無圧縮に近い取得**: ewfacquire は `-c method:level` のため **`deflate:none`** を使用（`none:none` ではない）。
- **E01 取得中の一時停止**: 現在の E01 パスは `ewfacquire` subprocess のみで、**RAW イメージングと同様の pause/resume は未対応**の可能性が高いです。計画の D-06 は主に RAW 向けとみなしてください。
- **B-05（E01 未設定時）**: 実装は **E01 オプションを一覧に出さない**方式です（グレーアウトではなく非表示＋案内文）。

## パーサーゲートの実行例

リポジトリルートで:

```powershell
python tests/integration/test_stdout_parser.py tests/integration/ewfacquire_stdout_sample.txt
```

実機で取得したログを `D:\logs\ewfacquire_run1.txt` に保存した場合:

```powershell
python tests/integration/test_stdout_parser.py D:\logs\ewfacquire_run1.txt
```

終了コード 0 で全パターンが少なくとも 1 回マッチしたことを意味します。
