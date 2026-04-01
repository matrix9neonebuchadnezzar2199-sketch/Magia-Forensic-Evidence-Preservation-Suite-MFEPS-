# Changelog

All notable changes to MFEPS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03-31

### Added (Sprint C)

- **ewfinfo 連携**: E01 取得後に `ewfinfo` を実行し、メタデータを `job.notes`（JSON）・UI・PDF/HTML 報告書に反映
- `src/core/e01_writer.py`: `E01InfoResult`、`info()`、`_parse_ewfinfo_output()`
- `src/utils/constants.py`: `EWFINFO_KV_PATTERN` / `EWFINFO_SECTION_PATTERN`
- `config.py`: `resolve_ewfinfo_path()`（`libs/` および `ewftools-x64` 自動検出）
- `tests/test_ewfinfo.py`（パーサー 6 件）、`tests/test_ewfinfo_integration.py`（`info()` モック 2 件）
- `docs/pyewf_fallback_design.md`: Phase 3 での pyewf / ctypes フォールバック設計

### Added
- **E01 出力**: ewfacquire subprocess による E01 (EWF) イメージ取得
- `src/core/e01_writer.py`: E01Writer クラス（取得・検証・キャンセル）
- `tests/test_e01_writer.py`: E01 パーサー・コマンド生成テスト 17 件
- `tests/test_imaging_service.py`: on_imaging_complete 永続化テスト 2 件
- `tests/test_buffer_manager.py`: DoubleBufferManager EOF・キャンセルテスト 3 件
- `tests/integration/`: ewfacquire stdout パーサー統合テスト基盤
- `libs/README_ewftools.md`: ewfacquire / ewfverify 配置手順
- E01 設定カード（圧縮 / セグメントサイズ / EWF フォーマット選択）
- USB/HDD ウィザードに RAW / E01 フォーマット選択追加
- HTML / PDF 報告書に E01 セクション追加
- エラーコード E7001〜E7006（E01 出力関連）
- `ImagingJob` に E01 関連 DB カラム 9 個追加
- `config.py` に `resolve_ewfacquire_path()` / `resolve_ewfverify_path()` 自動検出
- `.env.example` に E01 設定項目追加
- `THIRD_PARTY_LICENSES.md` に libewf LGPL-3.0+ 追記

### Changed
- `APP_VERSION` を "2.1.0" に更新
- `layout.py` / `main.py` を `APP_VERSION` 定数参照にリファクタ
- `OutputFormat` enum に `E01` を追加
- `imaging_service.py` に E01 分岐追加
- `total_bytes` / `copied_bytes` を `BigInteger` に変更（4GB 超デバイス対応）
- `EvidenceItem.device_capacity_bytes` を `BigInteger` に変更
- `on_imaging_complete()` で `error_code` / `error_message` を `job.notes` に永続化
- `DoubleBufferManager.read_loop` に EOF ガード（`if not data: break`）追加
- `optical_engine.py` の `image_optical` を `run_in_executor` でワーカースレッド実行に変更
- `optical_engine.py` の `_cancel_event` / `_pause_event` を `threading.Event` に変更
- E01 プログレスパーサーを `_read_stream_cr_aware`（`read(4096)` + CR/LF 両対応）に変更
- `E01_PROGRESS_PATTERN` を `([\d.]+)%` に修正（小数パーセント対応）
- `E01_ACQUIRED_PATTERN` / `E01_SPEED_PATTERN` を追加
- `get_progress()` で E01 の `acquired_bytes` / `total_bytes` / `speed_bytes` を返すよう修正
- ewfacquire 完了時に `acquired_bytes = total_bytes` に補正して 100% コールバック
- 光学イメージング完了時に `copied_bytes = total_bytes` に補正（99.9% 止まり対策）
- 光学イメージング完了時に source → verify ハッシュコピー（レポート「ハッシュ不一致」修正）
- `report_service.py`: 空ハッシュ行をスキップ、鑑識者未記入時「未記入」表示
- `legal_consent_dialog.py`: NiceGUI 3.9 の `on_change=` コンストラクタ方式に変更
- ewftools ビルドアーティファクト 59 ファイルを `.gitignore` に追加・`git rm --cached`
- README.md を v2.1.0 に全面更新: タイトル・E01 ハッシュ説明（SHA-1 不使用注記）・実機テスト結果・libewf 既知制限・ewftools 入手元・E01 環境変数・ER 図の BigInteger 反映・テスト件数
- `tests/integration/e01_test_results_20260331.md` を実機テスト結果で記入
- **光学メディア容量 (Sprint B-1)**: `OpticalAnalysisResult` に `ioctl_length_bytes` / `toc_leadout_bytes` / `capacity_source` を追加。容量は **TOC リードアウトを IOCTL より優先**（CD で IOCTL がリードアウト先を含む場合のずれを緩和）。`ImagingJob.notes` に容量診断 JSON を追記し、PDF/HTML レポートで申告容量と実読取の差分を表示
- **E01 ewfverify (Sprint B-2)**: `verify()` で `proc.communicate()` 後に subprocess transport を明示的に `close()`。`main.py` で Proactor の `ConnectionResetError`（pipe transport）を DEBUG ログに格下げ

### Removed
- E01 出力における SHA-1 ハッシュ（libewf 20230405 が外部出力しないため全面除去、MD5 + SHA-256 の 2 系に統一）

## [2.0.0] - 2026-03-30

### Added
- **Phase 1**: Legal consent modal with scroll-to-bottom requirement and audit logging
- **Phase 1**: CSS decryption integration via pydvdcss (optional, GPL-3.0)
- **Phase 1**: Sony ARccOS detection (99-track + bad-sector pattern scan)
- **Phase 2**: AACS decryption path via libaacs ctypes bindings
- **Phase 2**: Disney X-Project detection accuracy improvement (VTS count + size heuristics)
- **Phase 2**: Test infrastructure (pytest, 15 test cases) and GitHub Actions CI
- **Phase 3**: Local WebUI authentication (bcrypt + session management)
- **Phase 3**: MIT License with GPL-3.0 isolation for pydvdcss
- **Phase 3**: Bilingual README (Japanese + English)
- **Phase 3**: WriteBlocker limitation documentation in code, reports, and UI
- **Phase 4**: Expanded test suite (35+ test cases covering schema, config, reports, write-blocker, error codes)
- **Phase 4**: pyproject.toml for standardized packaging
- **Phase 4**: CHANGELOG.md

### Changed
- Audit log timestamps normalized to UTC (fixes hash-chain false positives)
- `copy_guard_analyzer.py` now imports pydvdcss only through `dvdcss_reader.py` (GPL isolation)
- `requirements.txt` restructured with pydvdcss as commented optional dependency

### Fixed
- Timezone-aware vs naive datetime comparison in `audit_service.verify_chain()`
- `overall_can_decrypt` logical AND issue resolved by per-protection `can_decrypt` checks
