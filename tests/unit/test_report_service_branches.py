"""report_service HTML/PDF 分岐の追加テスト"""
from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pytest


def _base_data(**overrides):
    d = {
        "case_number": "C1",
        "case_name": "Case",
        "examiner_name": "Ex",
        "evidence_number": "E1",
        "source_hashes": {"md5": "a", "sha256": "b", "sha512": ""},
        "verify_hashes": {"md5": "a", "sha256": "b", "sha512": ""},
        "match_result": "matched",
        "total_bytes": 100,
        "copied_bytes": 100,
        "elapsed_seconds": 1.0,
        "avg_speed": 10.0,
        "error_count": 0,
        "write_block_method": "hardware",
        "output_format": "raw",
        "e01_compression": "fast",
        "e01_segment_size_bytes": 1024,
        "e01_ewf_format": "EWF",
        "e01_examiner_name": "",
        "e01_segment_count": 2,
        "e01_ewfacquire_version": "1.0",
        "e01_command_line": "ewfacquire ...",
        "capacity_notes": "",
        "optical_info": None,
        "rfc3161": {"has_timestamp": False, "tsa_url": ""},
        "copy_guard_type": "",
        "copy_guard_detail": "",
        "ewfinfo": None,
    }
    d.update(overrides)
    return d


@patch("src.services.report_service.get_config")
def test_html_report_optical_info(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    oi = {
        "media_type": "dvd",
        "file_system": "udf",
        "sector_size": 2048,
        "capacity_bytes": 1000,
        "capacity_source": "ioctl",
        "track_count": 1,
    }
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(optical_info=oi),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "光学メディア情報" in text
    assert "dvd" in text


@patch("src.services.report_service.get_config")
def test_html_report_e01_section(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(
            output_format="e01",
            e01_ewf_format="EWF2",
        ),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "E01 取得情報" in text
    assert "EWF2" in text


@patch("src.services.report_service.get_config")
def test_html_report_ewfinfo_section(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    ewf = {
        "success": True,
        "version": "1.2",
        "sections": {"meta": {"k": "v"}},
    }
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(output_format="e01", ewfinfo=ewf),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "E01 メタデータ" in text
    assert "meta" in text


@patch("src.services.report_service.get_config")
def test_html_report_rfc3161_section(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(
            rfc3161={
                "has_timestamp": True,
                "tsa_url": "http://example.com/tsa",
            },
        ),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "RFC3161" in text
    assert "取得済み" in text


@patch("src.services.report_service.get_config")
def test_html_copy_guard_section(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(
            copy_guard_type="CSS",
            copy_guard_detail="detail<>&",
        ),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "コピーガード分析" in text
    assert "CSS" in text


@patch("src.services.report_service.get_config")
def test_html_capacity_notes_row(mock_cfg, tmp_path):
    from src.services.report_service import ReportService

    rdir = tmp_path / "reports"
    mock_cfg.return_value = MagicMock(reports_dir=rdir)
    notes = (
        '{"capacity_source": "x", "declared_capacity_bytes": 100, '
        '"actual_read_bytes": 50}'
    )
    svc = ReportService()
    with patch.object(
        svc,
        "_collect_report_data",
        return_value=_base_data(capacity_notes=notes),
    ):
        path = svc.generate_html("jid")
    text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
    assert "メディア申告容量" in text


def test_html_no_job_raises(tmp_path):
    from src.services.report_service import ReportService

    with patch("src.services.report_service.get_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(reports_dir=tmp_path / "r")
        svc = ReportService()
        with patch.object(svc, "_collect_report_data", return_value=None):
            with pytest.raises(ValueError, match="ジョブが見つかりません"):
                svc.generate_html("missing")


def test_pdf_raises_import_error_when_reportlab_missing(
    tmp_path, monkeypatch,
):
    from src.services.report_service import ReportService

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "reportlab" or name.startswith("reportlab."):
            raise ImportError("no reportlab")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with patch("src.services.report_service.get_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(reports_dir=tmp_path / "r")
        svc = ReportService()
        with patch.object(
            svc,
            "_collect_report_data",
            return_value=_base_data(),
        ):
            with pytest.raises(ImportError):
                svc.generate_pdf("jid")


@patch("src.services.report_service.get_config")
def test_generate_pdf_runs_full_pipeline(mock_cfg, tmp_path):
    """ReportLab PDF の主要分岐を一括で実行（カバレッジ用）"""
    from pathlib import Path

    from src.services.report_service import ReportService

    mock_cfg.return_value = MagicMock(reports_dir=tmp_path / "rep")
    notes = (
        '{"capacity_source": "x", "declared_capacity_bytes": 100, '
        '"actual_read_bytes": 50}'
    )
    data = _base_data(
        output_format="e01",
        match_result="matched",
        write_block_method="software",
        capacity_notes=notes,
        optical_info={
            "media_type": "dvd",
            "file_system": "udf",
            "sector_size": 2048,
            "capacity_bytes": 1000,
            "capacity_source": "ioctl",
            "track_count": 1,
        },
        rfc3161={"has_timestamp": True, "tsa_url": "http://example.com/tsa"},
        ewfinfo={
            "success": True,
            "version": "1.0",
            "sections": {"sec1": {"k1": "v1"}},
        },
        copy_guard_type="CSS",
        copy_guard_detail="detail text",
    )
    svc = ReportService()
    with patch.object(svc, "_collect_report_data", return_value=data):
        path = svc.generate_pdf("jid")
    assert Path(path).is_file()
    assert path.endswith(".pdf")


@patch("src.services.report_service.get_config")
def test_generate_pdf_mismatch_and_wb_none(mock_cfg, tmp_path):
    from pathlib import Path

    from src.services.report_service import ReportService

    mock_cfg.return_value = MagicMock(reports_dir=tmp_path / "rep2")
    data = _base_data(
        match_result="mismatched",
        write_block_method="none",
        source_hashes={"md5": "x", "sha256": "y"},
        verify_hashes={"md5": "a", "sha256": "b"},
    )
    svc = ReportService()
    with patch.object(svc, "_collect_report_data", return_value=data):
        path = svc.generate_pdf("jid2")
    assert Path(path).is_file()


@pytest.mark.parametrize(
    "wb",
    ("both", "hardware", "software", "none"),
)
@patch("src.services.report_service.get_config")
def test_generate_html_write_block_variants(mock_cfg, tmp_path, wb):
    from pathlib import Path

    from src.services.report_service import ReportService

    mock_cfg.return_value = MagicMock(reports_dir=tmp_path / f"html_{wb}")
    data = _base_data(write_block_method=wb)
    svc = ReportService()
    with patch.object(svc, "_collect_report_data", return_value=data):
        path = svc.generate_html(f"job-{wb}")
    text = Path(path).read_text(encoding="utf-8")
    assert "書き込み保護" in text


@patch("src.services.report_service.get_config")
def test_generate_pdf_write_block_both(mock_cfg, tmp_path):
    from pathlib import Path

    from src.services.report_service import ReportService

    mock_cfg.return_value = MagicMock(reports_dir=tmp_path / "pdf_wb")
    data = _base_data(write_block_method="both")
    svc = ReportService()
    with patch.object(svc, "_collect_report_data", return_value=data):
        path = svc.generate_pdf("jwbb")
    assert Path(path).is_file()
