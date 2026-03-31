# Changelog

All notable changes to MFEPS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03-31

### Added
- **E01 (Expert Witness Format)** imaging for USB/HDD via libewf `ewfacquire` subprocess (`src/core/e01_writer.py`)
- Settings page: E01 card (paths, connection test, default compression / segment size / EWF format) with `app.storage.general` overrides
- `ImagingJob` E01 columns and SQLite migrations; `OutputFormat.E01`; error codes E7001–E7006
- HTML/PDF report sections for E01 metadata; `libs/README_ewftools.md` and THIRD_PARTY_LICENSES entry for libewf
- Unit tests (`tests/test_e01_writer.py`) and integration-test documentation under `tests/integration/`

### Changed
- USB/HDD wizard: optional E01 output when `ewfacquire` is available

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
