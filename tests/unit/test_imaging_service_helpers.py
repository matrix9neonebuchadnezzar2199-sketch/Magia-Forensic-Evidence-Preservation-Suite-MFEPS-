"""imaging_service モジュールレベルヘルパーのテスト"""
from unittest.mock import MagicMock, patch

from src.core.imaging_engine import ImagingResult
from src.services import imaging_service as ims


def test_parse_e01_remaining_empty():
    assert ims._parse_e01_remaining_to_seconds("") == 0.0


def test_parse_e01_remaining_nomatch():
    assert ims._parse_e01_remaining_to_seconds("no match here") == 0.0


def test_parse_e01_remaining_parses():
    s = "completion in 1 minute(s) and 30 second(s)"
    assert ims._parse_e01_remaining_to_seconds(s) == 90.0


def test_hash_dict_has_values():
    assert ims._hash_dict_has_values({}) is False
    assert ims._hash_dict_has_values({"md5": ""}) is False
    assert ims._hash_dict_has_values({"md5": "a"}) is True


def test_merge_e01_verify_no_verify_hashes():
    r = ImagingResult(job_id="j", verify_hashes=None)
    assert ims._merge_e01_verify_hashes_from_source(None, r) is None


def test_merge_e01_non_e01():
    job = MagicMock()
    job.output_format = "raw"
    r = ImagingResult(
        job_id="j",
        verify_hashes={"md5": "a"},
        match_result="matched",
        source_hashes={"md5": "a"},
    )
    out = ims._merge_e01_verify_hashes_from_source(job, r)
    assert out == {"md5": "a"}


def test_merge_e01_fills_missing_md5():
    job = MagicMock()
    job.output_format = "e01"
    r = ImagingResult(
        job_id="j",
        verify_hashes={"md5": "", "sha256": "x"},
        match_result="matched",
        source_hashes={"md5": "srcmd5", "sha256": "x"},
    )
    out = ims._merge_e01_verify_hashes_from_source(job, r)
    assert out["md5"] == "srcmd5"


def test_schedule_progress_publish_no_loop():
    with patch("asyncio.get_running_loop", side_effect=RuntimeError), patch(
        "asyncio.get_event_loop", side_effect=RuntimeError
    ):
        ims._schedule_progress_publish("j1", {"x": 1})


def test_schedule_progress_publish_creates_task():
    loop = MagicMock()
    with patch("asyncio.get_running_loop", return_value=loop), patch(
        "src.services.progress_broadcaster.get_broadcaster"
    ) as gb:
        gb.return_value.publish = MagicMock(return_value=MagicMock())
        ims._schedule_progress_publish("j1", {"ok": True})
        loop.create_task.assert_called_once()
