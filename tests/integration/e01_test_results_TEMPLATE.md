# E01 実機統合テスト結果（テンプレート）

コピーして `e01_test_results_YYYYMMDD.md` として編集する。

## メタ

- 実行期間:
- MFEPS コミット:
- ewfacquire / ewfverify バージョン:

## テストケース記録

### [TC# 例: A-01]

- 実行日時:
- ステータス: SUCCESS / FAILED / SKIPPED
- 入力: ソースデバイス、圧縮、セグメント、フォーマット
- 出力ファイル一覧:
- セグメント数:
- 所要時間:
- ハッシュ: リファレンス vs 取得結果 → MATCH / MISMATCH
- ewfverify: SUCCESS / FAILED / SKIPPED
- 合格判定: PASS / FAIL
- 備考:

（以下、計画書の TC ごとに行を追加）

## パーサーゲート（E-01〜E-05）

- `test_stdout_parser.py` 実行結果: PASS / FAIL
- 修正した `constants.py` コミット: （該当時）

## ブロッカー

- （なし / 内容）
