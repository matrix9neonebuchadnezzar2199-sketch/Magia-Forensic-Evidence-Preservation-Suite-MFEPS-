# v2.1.1 実機回帰テスト手順書

## 前提条件
- Windows 10/11 x64、管理者権限
- Python 3.13、MFEPS コミット `46973a7`（main 先端。機能ベースは `c0cfcbb` を含む）
- ewfacquire/ewfverify/ewfinfo 20230405 を libs/ に配置
- USB メモリ（4 GB 以上）接続済み
- 光学ドライブ + データ CD/DVD（任意）

## テスト一覧

### R-01: pytest 全件通過
```
pytest tests/ -q
```
期待: 100 passed

### R-02: USB E01 取得（回帰）
1. 管理者で `python src/main.py` 起動
2. USB/HDD ウィザード → デバイス選択 → E01 形式
3. EnCase 6, deflate:fast, セグメント 1.4 GiB
4. 取得完了まで待機

確認事項:
- [ ] プログレスバーが 0% → 100% まで正常に動く
- [ ] ETA（残り時間）が表示される（Sprint A の新機能）
- [ ] MD5/SHA-256 が表示される
- [ ] ewfverify が SUCCESS を返す
- [ ] ewfinfo メタデータが Step 4 の結果画面に表示される（Sprint C の新機能）
- [ ] PDF レポートに E01 メタデータセクションが含まれる
- [ ] DB の imaging_jobs レコードに notes JSON が記録されている

ハッシュ参照値（同一 USB なら一致するはず）:
- MD5: `fe00fe0ce5792f54c069b2917c6082cf`
- SHA-256: `1c3b0858c395d278277ec944b768be4ed1b6d2dc9eae459b3f2baffe71930f26`

### R-03: ewfinfo 出力形式確認
```
.\libs\ewfinfo.exe <出力された.E01ファイル>
```
確認事項:
- [ ] セクション見出し（`Acquiry information:` 等）がコロン + 改行で終わる
- [ ] KV ペアがタブインデント + コロン区切りである
- [ ] `Digest hash information:` セクションに MD5 が存在する
- [ ] stdout をコピーして EWFINFO_KV_PATTERN / EWFINFO_SECTION_PATTERN でパースできる

**重要**: 出力形式がサンプルと異なる場合、stdout 全文を記録し、パターン修正が必要。

### R-04: ewfinfo 長パス検証
1. 出力先を `F:\very\long\path\name\that\exceeds\240\characters\...` に設定
2. E01 取得を実行
3. ewfinfo ステップでエラーが出ることを確認

確認事項:
- [ ] ewfinfo エラーがログに WARNING として記録される
- [ ] 取得自体は成功する（ewfinfo 失敗は致命的でない）
- [ ] UI に ewfinfo スキップのメッセージが表示されるか、カードが非表示

### R-05: CD ISO 取得（回帰）
1. データ CD を挿入
2. 光学メディアウィザード → ISO 取得
3. 完了まで待機

確認事項:
- [ ] プログレスバー 0% → 100%
- [ ] ハッシュ一致
- [ ] 容量診断情報が job.notes に記録される（Sprint B-1 の新機能）
- [ ] PDF レポートに申告容量 vs 実読取の行が表示される（差分がある場合）

ハッシュ参照値（同一 CD なら一致するはず）:
- MD5: `2a05c21dc45c33b719b659045aa55571`
- SHA-256: `b3b547298487a451ce7f6c4c6cd01164e2b2a37fdb455b54dfbf2c37d08176d8`

### R-06: 光学 E01 可否判定
```
.\libs\ewfacquire.exe \\.\CdRom0 -t test_optical -u -f encase6 -c deflate:fast
```
結果:
- 成功 → Sprint B-3 実装可能、Phase 3 で対応
- 失敗 → B-3 は ewfacquire の制限として文書化

### R-07: ConnectionResetError 確認
1. USB E01 取得 + ewfverify を実行
2. `logs/app.log` を確認

確認事項:
- [ ] `ConnectionResetError` が ERROR レベルで出力されない
- [ ] DEBUG レベルに格下げされているか、完全に消えている

### R-08: キャンセル動作確認
1. USB E01 取得を開始
2. 進捗 10〜30% でキャンセルボタンを押す

確認事項:
- [ ] ewfacquire プロセスが終了する
- [ ] ステータスが「キャンセル」になる
- [ ] DB に cancelled ステータスが記録される
- [ ] 部分的な E01 ファイルが残る（削除しない仕様）

## 結果テンプレート

| ID | 項目 | 結果 | 備考 |
|----|------|------|------|
| R-01 | pytest | PASS / FAIL | 件数: |
| R-02 | USB E01 回帰 | PASS / FAIL | MD5: / ETA表示: Y/N / ewfinfo: Y/N |
| R-03 | ewfinfo 形式確認 | PASS / FAIL | パターン一致: Y/N |
| R-04 | ewfinfo 長パス | PASS / FAIL | WARNING記録: Y/N |
| R-05 | CD ISO 回帰 | PASS / FAIL | 容量診断: Y/N |
| R-06 | 光学 E01 判定 | 成功 / 失敗 | エラー内容: |
| R-07 | ConnReset 確認 | PASS / FAIL | ログレベル: |
| R-08 | キャンセル動作 | PASS / FAIL | |

## ゲート基準
- R-01〜R-05、R-07、R-08 が全て PASS → リリース可
- R-03 で形式不一致 → パターン修正後に再テスト
- R-06 は情報収集のみ（PASS/FAIL を問わずリリースに影響なし）
