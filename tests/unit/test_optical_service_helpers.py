"""optical_service モジュールレベルヘルパー"""
from unittest.mock import MagicMock, patch

from src.services import optical_service as osvc


def test_schedule_optical_progress_publish_no_loop():
    with patch("asyncio.get_running_loop", side_effect=RuntimeError), patch(
        "asyncio.get_event_loop", side_effect=RuntimeError
    ):
        osvc._schedule_optical_progress_publish("j1", {"x": 1})


def test_schedule_optical_progress_publish_task():
    loop = MagicMock()
    with patch("asyncio.get_running_loop", return_value=loop), patch(
        "src.services.progress_broadcaster.get_broadcaster"
    ) as gb:
        gb.return_value.publish = MagicMock(return_value=MagicMock())
        osvc._schedule_optical_progress_publish("j1", {"ok": True})
        loop.create_task.assert_called_once()
