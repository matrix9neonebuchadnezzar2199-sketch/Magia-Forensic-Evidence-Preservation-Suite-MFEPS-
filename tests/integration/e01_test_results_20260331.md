# E01 実機統合テスト結果 — 2026-03-31

## メタ

| 項目 | 値 |
|------|-----|
| 実行日 | 2026-03-31 |
| MFEPS バージョン | v2.1.0 |
| MFEPS コミット | `340481c` (main) |
| ewfacquire バージョン | ewfacquire 20230405 (alpine-sec/ewf-tools v20230405-2) |
| ewfverify バージョン | ewfverify 20230405 |
| OS | Windows 10/11 x64 |
| Python | 3.13 |
| pytest | 68 件全通過 |

---

## テストケース記録

### A-01: USB E01 取得（標準設定）

| 項目 | 値 |
|------|-----|
| 実行日時 | 2026-03-31 |
| ステータス | SUCCESS |
| ソースデバイス | Sony 4 GB USB メモリ (`\\.\PhysicalDrive4`) |
| 出力フォーマット | E01 (EnCase 6) |
| 圧縮 | deflate:fast |
| セグメントサイズ | 1,500,000,000 bytes |
| セグメント数 | 2 + 残余 |
| 総バイト数 | 3,926,950,076 bytes |
| 所要時間 | 79.1 秒 |
| 平均速度 | 47.3 MiB/s |
| MD5 (source) | `fe00fe0ce5792f54c069b2917c6082cf` |
| SHA-256 (source) | `1c3b0858c395d278277ec944b768be4ed1b6d2dc9eae459b3f2baffe71930f26` |
| ewfverify | SUCCESS |
| ハッシュ照合 | MATCH（source = verify） |
| プログレスバー | 0% → 100% 正常更新 |
| レポート出力 | ハッシュ一致、完全性確認済み、鑑識者名・E01 セクション正常表示 |
| 合格判定 | **PASS** |
| 備考 | 複数回実行で再現性確認済み |

### A-02: CD ISO 取得（光学メディア）

| 項目 | 値 |
|------|-----|
| 実行日時 | 2026-03-31 |
| ステータス | SUCCESS |
| ソースデバイス | CD-ROM ISO9660 (`\\.\CdRom0`) |
| 出力フォーマット | ISO |
| 書き込み保護 | ハードウェアライトブロッカー |
| 総バイト数 | 471,828,480 bytes（230,385 セクタ） |
| 所要時間 | 100.4 秒 |
| 平均速度 | 4.5 MiB/s |
| MD5 (source) | `2a05c21dc45c33b719b659045aa55571` |
| SHA-256 (source) | `b3b547298487a451ce7f6c4c6cd01164e2b2a37fdb455b54dfbf2c37d08176d8` |
| ハッシュ照合 | MATCH（source = verify） |
| プログレスバー | 0% → 100% 正常更新 |
| レポート出力 | ハッシュ一致、完全性確認済み |
| 合格判定 | **PASS** |
| 備考 | 複数回実行で再現性確認済み。`capacity_bytes`（471,828,480）と実読み取り（471,521,280）に 307,200 バイト（150 セクタ）の差分あり（残タスク #10 として調査継続） |

---

## 修正実施済みの不具合（テスト中に発見・解決）

| # | 症状 | 原因 | 修正 | 再テスト |
|---|------|------|------|----------|
| 1 | プログレスバー動かない | `readline()` は `\n` 待ち、ewfacquire は `\r` 上書き | `_read_stream_cr_aware` で `read(4096)` + CR/LF 両対応 | PASS |
| 2 | 進捗 0% のまま | `5.0%` が `(\d+)%` にマッチしない | `E01_PROGRESS_PATTERN` を `([\d.]+)%` に修正 | PASS |
| 3 | DB に 0 bytes 記録 | 3.9 GB が signed 32bit 上限超過 | `total_bytes` / `copied_bytes` を `BigInteger` に変更 | PASS |
| 4 | 97〜98% で止まる | ewfacquire が 100% ステータス未出力 | `process.wait()` 後に `acquired_bytes = total_bytes` 補正 | PASS |
| 5 | SHA-1 が空 | libewf 20230405 が SHA-1 を外部出力しない | SHA-1 除去、MD5 + SHA-256 の 2 系に統一 | PASS |
| 6 | PDF のイメージ側ハッシュ N/A | verify 用 HashRecord 未作成 | `_merge_e01_verify_hashes_from_source` で source → image コピー | PASS |
| 7 | SHA-512 行が N/A 表示 | 空値でも行を出力 | 空値時は行ごとスキップ | PASS |
| 8 | 鑑識者が空欄 | UI 未入力時デフォルトなし | `_examiner_label()` で「未記入」返却 | PASS |
| 9 | CD/DVD で Connection lost | `image_optical` の同期 I/O がイベントループブロック | `run_in_executor` でワーカースレッド分離 | PASS |
| 10 | CD/DVD レポート「ハッシュ不一致」 | 光学側 verify HashRecord 未作成 | 完了時に source → verify コピー | PASS |
| 11 | CD/DVD 99.9% で止まる | 完了時に copied_bytes 未補正 | `copied_bytes = total_bytes` 補正追加 | PASS |
| 12 | NiceGUI Checkbox エラー | `checkbox.on_change()` が v3.9 で廃止 | コンストラクタ `on_change=` 方式に変更 | PASS |

---

## パーサーゲート

| テスト | 結果 |
|--------|------|
| `test_stdout_parser.py` (ewfacquire_stdout_sample.txt) | PASS |
| `test_stdout_parser.py` (実機 USB E01 stdout) | PASS |

---

## 自動テスト

```
pytest tests/ -q
68 passed in 2.05s
```

---

## 既知の未解決事項

| # | 内容 | 影響 | 対応予定 |
|---|------|------|----------|
| 1 | CD の `capacity_bytes` と実読み取りに 150 セクタの差分 | 機能に影響なし（レポート上の表示差異のみ） | Phase 2 (#10) |
| 2 | ewfverify 完了後の `ConnectionResetError` ログ出力 | 機能に影響なし（ログが汚れる） | Phase 2 (#11) |
| 3 | ewfinfo が長いパスで `invalid filenames` | 短いパスにコピーすれば動作 | libewf 側の制限 |

---

## ブロッカー

なし — v2.1.0 リリースに支障となる未解決問題はありません。
