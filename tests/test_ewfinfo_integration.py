"""E01Writer.info() の subprocess モック統合テスト"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


from src.core.e01_writer import E01Writer
from tests.test_ewfinfo import TestEwfinfoParser


class TestEwfinfoMethod:
    """Test E01Writer.info() with mocked subprocess."""

    async def _info_success_body(self, ewfinfo_exe: Path):
        writer = E01Writer()

        async def fake_exec(*_a, **_kw):
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock(
                return_value=(
                    TestEwfinfoParser.SAMPLE_OUTPUT.encode("utf-8"),
                    b"",
                )
            )
            mock_proc.returncode = 0
            mock_proc._transport = None
            return mock_proc

        with patch.object(
            E01Writer,
            "_resolve_ewfinfo_path",
            return_value=str(ewfinfo_exe),
        ):
            with patch(
                "src.core.e01_writer.asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ):
                result = await writer.info("test.E01")
                assert result.success
                assert result.case_number == "CASE-001"
                assert result.digest_md5 == "fe00fe0ce5792f54c069b2917c6082cf"

    def test_info_success(self, tmp_path):
        exe = tmp_path / "ewfinfo.exe"
        exe.write_bytes(b"")
        asyncio.run(self._info_success_body(exe))

    async def _info_not_found_body(self):
        writer = E01Writer()
        with patch.object(E01Writer, "_resolve_ewfinfo_path", return_value=""):
            result = await writer.info("test.E01")
            assert not result.success
            assert "not found" in result.error_message.lower()

    def test_info_not_found(self):
        asyncio.run(self._info_not_found_body())
