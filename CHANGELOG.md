# Changelog

All notable changes to MFEPS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03-31

### Added
- **E01 出力**: ewfacquire subprocess による E01 (EWF) 形式イメージ取得
- `src/core/e01_writer.py`: E01Writer ラッパー（取得・検証・キャンセル）
- `tests/test_e01_writer.py`: 17 件のユニットテスト
- `tests/integration/`: 実機統合テストスイート（パーサーゲート、テンプレート）
- `libs/README_ewftools.md`: ewfacquire / ewfverify 導入ガイド
- 設定画面に E01 出力カード（パス設定・接続テスト・圧縮 / セグメント / フォーマット選択）
- USB/HDD 画面に出力形式選択（RAW / E01）と E01 設定サブパネル
- HTML / PDF レポートに E01 メタ情報セクション
- E7001–E7006 エラーコード（E01 関連）
- `ImagingJob` に E01 固有 DB カラム 9 件 + 自動マイグレーション
- `.env.example` に E01 設定項目
- `THIRD_PARTY_LICENSES.md` に libewf LGPL-3.0+

### Changed
- `APP_VERSION` を 2.1.0 に更新
- `layout.py` サイドバー / フッターのバージョン表記を `APP_VERSION` 定数参照に変更
- `OutputFormat` enum に `E01` を追加
- `imaging_service.py` に E01 分岐と監査ログ連携を追加

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
