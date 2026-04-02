"""CopyGuardAnalyzer と OpticalImagingEngine / OpticalService 連携（Phase 4-2）"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.copy_guard_analyzer import CopyGuardAnalyzer, CopyGuardResult, ProtectionInfo
from src.core.optical_engine import (
    OpticalAnalysisResult,
    OpticalImagingEngine,
    OpticalImagingResult,
)
from src.models.database import get_session, init_database
from src.models.enums import CopyGuardType
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.optical_service import OpticalService


@pytest.fixture
def opt_db(tmp_path):
    init_database(tmp_path / "cg.db")
    session = get_session()
    case = Case(case_number="CG", case_name="c")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="E", media_type="dvd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="job-cg-1",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\D:",
        output_path=str(tmp_path / "o.iso"),
        output_format="iso",
    )
    session.add(job)
    session.commit()
    return {"job_id": job.id, "tmp_path": tmp_path}


def _dvd_analysis():
    return OpticalAnalysisResult(
        capacity_bytes=2048,
        sector_count=1,
        sector_size=2048,
        capacity_source="t",
        media_type="DVD-Video",
    )


class TestOpticalEngineCopyGuard:
    def test_css_detection_enables_pydvdcss(self, tmp_path):
        out = str(tmp_path / "out.iso")
        cgr = CopyGuardResult(
            protections=[
                ProtectionInfo(
                    type=CopyGuardType.CSS.value,
                    detected=True,
                    can_decrypt=True,
                )
            ],
            overall_can_decrypt=True,
        )
        inst = MagicMock()
        inst.is_scrambled = False
        inst.read_sectors = MagicMock(return_value=b"\x00" * 2048)
        inst.open = MagicMock()
        inst.close = MagicMock()

        with patch("src.core.dvdcss_reader.DvdCssReader", return_value=inst):
            eng = OpticalImagingEngine(buffer_sectors=1)
            result = asyncio.run(
                eng.image_optical(
                    r"\\.\D:",
                    out,
                    _dvd_analysis(),
                    use_pydvdcss=False,
                    use_aacs=False,
                    copy_guard_result=cgr,
                )
            )
        assert result.decrypt_method == "pydvdcss"
        inst.open.assert_called_once()

    def test_aacs_cannot_decrypt_falls_back_raw(self, tmp_path):
        out = str(tmp_path / "out.iso")
        cgr = CopyGuardResult(
            protections=[
                ProtectionInfo(
                    type=CopyGuardType.AACS.value,
                    detected=True,
                    can_decrypt=False,
                )
            ],
            overall_can_decrypt=False,
        )
        fake_handle = object()

        with patch(
            "src.core.optical_engine.open_device", return_value=fake_handle
        ) as od, patch(
            "src.core.optical_engine.read_sectors",
            return_value=b"\x00" * 2048,
        ) as rs, patch(
            "src.core.optical_engine.close_device"
        ) as cd:
            eng = OpticalImagingEngine(buffer_sectors=1)
            result = asyncio.run(
                eng.image_optical(
                    r"\\.\D:",
                    out,
                    _dvd_analysis(),
                    use_pydvdcss=False,
                    use_aacs=True,
                    copy_guard_result=cgr,
                )
            )
        assert result.status == "completed"
        assert result.decrypt_method is None
        od.assert_called_once()
        rs.assert_called()
        cd.assert_called_once_with(fake_handle)


class TestCopyGuardAnalyzerTimeout:
    def test_analyze_timeout_skips_with_empty_result(self, monkeypatch):
        def slow_body(self, *a, **k):
            time.sleep(2.0)
            return CopyGuardResult()

        monkeypatch.setattr(CopyGuardAnalyzer, "_analyze_body", slow_body)
        an = CopyGuardAnalyzer()
        r = an.analyze(
            r"\\.\D:",
            OpticalAnalysisResult(media_type="CD-ROM"),
            timeout=0.15,
        )
        assert r.protections == []
        assert "タイムアウト" in r.recommended_action


class TestOpticalServiceAnalyzerFailure:
    def test_analyzer_exception_passes_none_to_engine(self, opt_db, tmp_path, monkeypatch):
        mock_cls = MagicMock()
        mock_cls.return_value.analyze.side_effect = RuntimeError("analyzer boom")
        monkeypatch.setattr(
            "src.core.copy_guard_analyzer.CopyGuardAnalyzer",
            mock_cls,
        )

        captured = {}

        async def capture_image_optical(**kwargs):
            captured["copy_guard_result"] = kwargs.get("copy_guard_result")
            return OpticalImagingResult(
                status="completed",
                source_hashes={},
                copied_bytes=100,
                total_bytes=100,
                elapsed_seconds=0.1,
                output_path=str(tmp_path / "o.iso"),
            )

        svc = OpticalService()
        jid = opt_db["job_id"]
        svc._progress[jid] = {
            "status": "pending",
            "copied_bytes": 0,
            "total_bytes": 1000,
            "speed_mibps": 0.0,
            "eta_seconds": 0,
            "error_count": 0,
            "current_file": r"\\.\D:",
        }
        eng = MagicMock()
        eng.image_optical = AsyncMock(side_effect=capture_image_optical)
        eng._cancel_event = MagicMock()
        svc._job_actors[jid] = "Actor"

        async def _run():
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\D:",
                str(tmp_path / "o.iso"),
                _dvd_analysis(),
                False,
                False,
                lambda x: None,
                verify=False,
            )

        asyncio.run(_run())
        assert captured.get("copy_guard_result") is None
