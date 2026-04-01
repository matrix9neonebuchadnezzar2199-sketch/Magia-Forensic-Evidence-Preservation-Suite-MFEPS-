# MFEPS v2.1.1 — ewfinfo Integration & Hardening

**Release date**: 2026-04-01  
**Commit**: c0cfcbb (main)  
**Previous release**: v2.1.0 (6080b85)  
**Tests**: 100 passed  

## Highlights

### ewfinfo Metadata Extraction (Sprint C)
After E01 acquisition, MFEPS now optionally runs `ewfinfo` to parse
embedded metadata (case number, evidence number, examiner, media size,
compression, digest hashes) and displays it in:
- The imaging result panel (Step 4 of USB/HDD wizard)
- PDF and HTML forensic reports
- `ImagingJob.notes` as JSON for audit trail

### ETA Display for E01 Acquisition (Sprint A)
`get_progress()` now returns `eta_seconds` parsed from ewfacquire's
"completion in X minute(s) and Y second(s)" output. The UI progress
panel can display remaining time during E01 acquisition.

### Negative Test Suite (Sprint A)
15 new failure-scenario tests covering: RAW/E01 cancellation (E3006),
disk full (E1004), permission denied, ewfacquire missing (E7001),
ewfacquire process failure (E7002), device read errors, and cancel
persistence across sessions.

### Optical Media Capacity Diagnostics (Sprint B-1)
`OpticalAnalysisResult` now tracks `ioctl_length_bytes`,
`toc_leadout_bytes`, and `capacity_source`. Capacity is selected via
TOC lead-out → IOCTL → TOC max_lba priority, mitigating the 150-sector
discrepancy observed on CD media. Reports show declared vs actual
capacity when they differ.

### ConnectionResetError Mitigation (Sprint B-2)
`e01_writer.verify()` now explicitly closes the subprocess transport
after `communicate()`. An asyncio exception handler in `main.py`
downgrades Proactor pipe `ConnectionResetError` to DEBUG level.

### pyewf Fallback Design (Sprint C)
`docs/pyewf_fallback_design.md` documents the Phase 3 plan for a
`PyEwfWriter` class using pyewf bindings or libewf.dll ctypes as a
fallback when ewfacquire is unavailable.

## Files Changed (vs v2.1.0)
- 18 files changed across 3 commits
- New files: `tests/test_negative.py`, `tests/test_ewfinfo.py`,
  `tests/test_ewfinfo_integration.py`, `tests/test_optical_capacity.py`,
  `docs/pyewf_fallback_design.md`
- Modified: `constants.py`, `config.py`, `e01_writer.py`,
  `imaging_service.py`, `optical_engine.py`, `optical_service.py`,
  `report_service.py`, `main.py`, `usb_hdd.py`, `test_e01_writer.py`,
  `CHANGELOG.md`

## Test Summary
| Suite | Count |
|-------|-------|
| E01 writer + ETA parser | 22 |
| Negative scenarios | 15 |
| ewfinfo parser | 6 |
| ewfinfo integration | 2 |
| Optical capacity | 3 |
| Existing (imaging, schema, config, etc.) | 52 |
| **Total** | **100** |

## Known Issues
- CD capacity 150-sector discrepancy is diagnosed but root cause
  (IOCTL vs TOC lead-out) varies by drive firmware
- ewfinfo fails on long Windows paths (>240 chars); MFEPS logs a
  warning and skips metadata extraction
- Optical E01 (B-3) pending real-device `ewfacquire \\.\CdRom0` test
- v2.1.0 tag remains at 6080b85 for traceability

## Upgrade Notes
- No database migration required (new fields use existing ALTER TABLE
  migration in `database.py`)
- No new `.env` variables required (`EWFINFO_PATH` is optional;
  auto-detected from `libs/`)
- ewfinfo.exe placement: same location as ewfacquire.exe (`libs/`
  or `libs/ewftools-x64/`)
