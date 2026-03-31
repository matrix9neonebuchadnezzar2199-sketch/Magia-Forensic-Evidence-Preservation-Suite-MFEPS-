"""
MFEPS v2.0 — E01Writer 単体テスト
"""
import asyncio
import re
from unittest.mock import MagicMock, patch

from src.core.e01_writer import E01Params, E01Writer
from src.utils.constants import (
    E01_ACQUIRED_PATTERN,
    E01_BYTES_PATTERN,
    E01_PROGRESS_PATTERN,
    E01_SPEED_PATTERN,
    EWFVERIFY_COMPUTED_HASH_PATTERN,
    EWFVERIFY_STORED_HASH_PATTERN,
    EWFVERIFY_SUCCESS_PATTERN,
)


class TestCheckAvailable:
    def test_not_configured(self):
        with patch("src.core.e01_writer.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.ewfacquire_path = ""
            cfg.ewfverify_path = ""
            cfg.resolve_ewfacquire_path = MagicMock(return_value="")
            cfg.resolve_ewfverify_path = MagicMock(return_value="")
            mock_cfg.return_value = cfg

            result = E01Writer.check_available()
            assert result["ewfacquire_available"] is False
            assert result["ewfverify_available"] is False

    def test_path_configured_but_missing(self):
        with patch("src.core.e01_writer.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.ewfacquire_path = "/nonexistent/ewfacquire.exe"
            cfg.ewfverify_path = ""
            cfg.resolve_ewfacquire_path = MagicMock(return_value="")
            cfg.resolve_ewfverify_path = MagicMock(return_value="")
            mock_cfg.return_value = cfg

            result = E01Writer.check_available()
            assert result["ewfacquire_available"] is False


class TestBuildCommand:
    def test_basic_command(self):
        with patch("src.core.e01_writer.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.ewfacquire_path = r"C:\libs\ewfacquire.exe"
            cfg.resolve_ewfacquire_path = MagicMock(
                return_value=r"C:\libs\ewfacquire.exe"
            )
            mock_cfg.return_value = cfg

            writer = E01Writer()
            params = E01Params(
                source_path=r"\\.\PhysicalDrive1",
                output_dir=r"C:\output\case001",
                output_basename="image",
                case_number="CASE-001",
                evidence_number="EV-001",
                examiner_name="Taro Yamada",
                compression_method="deflate",
                compression_level="fast",
                segment_size_bytes=1_500_000_000,
                sectors_per_chunk=64,
                ewf_format="encase6",
                media_type="removable",
                media_flags="physical",
                zero_on_error=True,
                calculate_sha1=True,
                calculate_sha256=True,
            )
            cmd, log_path = writer.build_command(params)

            assert cmd[0] == r"C:\libs\ewfacquire.exe"
            assert "-t" in cmd
            assert cmd[cmd.index("-t") + 1].endswith("image")
            assert "-u" in cmd
            assert "-w" in cmd

            idx_c = cmd.index("-C")
            assert cmd[idx_c + 1] == "CASE-001"

            idx_e = cmd.index("-E")
            assert cmd[idx_e + 1] == "EV-001"

            idx_comp = cmd.index("-c")
            assert cmd[idx_comp + 1] == "deflate:fast"

            idx_s = cmd.index("-S")
            assert cmd[idx_s + 1] == "1500000000"

            idx_f = cmd.index("-f")
            assert cmd[idx_f + 1] == "encase6"

            d_indices = [i for i, x in enumerate(cmd) if x == "-d"]
            d_values = [cmd[i + 1] for i in d_indices]
            assert "sha1" in d_values
            assert "sha256" in d_values

            assert cmd[-1] == r"\\.\PhysicalDrive1"

            assert "-l" in cmd
            assert "ewfacquire.log" in log_path

    def test_no_zero_on_error(self):
        with patch("src.core.e01_writer.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.ewfacquire_path = "ewfacquire"
            cfg.resolve_ewfacquire_path = MagicMock(return_value="ewfacquire")
            mock_cfg.return_value = cfg

            writer = E01Writer()
            params = E01Params(
                source_path="/dev/sdb",
                output_dir="/tmp",
                zero_on_error=False,
                calculate_sha1=False,
                calculate_sha256=False,
            )
            cmd, _ = writer.build_command(params)
            assert "-w" not in cmd
            assert "-d" not in cmd


class TestOutputParsing:
    def test_extract_md5(self):
        output = (
            "Acquiry completed at: Sun Aug  5 11:32:42 2012\n"
            "Written: 1.4 MiB (1474560 bytes) in 1 second(s).\n"
            "MD5 hash calculated over data:\t"
            "ae1ce8f5ac079d3ee93f97fe3792bda3\n"
        )
        assert (
            E01Writer._extract_hash_from_output(output, "MD5")
            == "ae1ce8f5ac079d3ee93f97fe3792bda3"
        )

    def test_extract_sha1(self):
        output = (
            "SHA1 hash calculated over data:\tab12cd34ef5678901234567890abcdef12345678\n"
        )
        assert (
            E01Writer._extract_hash_from_output(output, "SHA1")
            == "ab12cd34ef5678901234567890abcdef12345678"
        )

    def test_extract_sha1_hyphenated_label(self):
        """libewf は "SHA-1 hash calculated" と出力する場合がある"""
        output = (
            "SHA-1 hash calculated over data:\tab12cd34ef5678901234567890abcdef12345678\n"
        )
        assert (
            E01Writer._extract_hash_from_output(output, "SHA1")
            == "ab12cd34ef5678901234567890abcdef12345678"
        )

    def test_extract_sha256(self):
        sha = "a" * 64
        output = f"SHA256 hash calculated over data: {sha}\n"
        assert E01Writer._extract_hash_from_output(output, "SHA256") == sha

    def test_extract_hash_missing(self):
        assert E01Writer._extract_hash_from_output("no hash here", "MD5") == ""

    def test_extract_written_bytes(self):
        output = (
            "Written: 1.4 MiB (1474560 bytes) in 1 second(s) with 1 MiB/s.\n"
        )
        assert E01Writer._extract_written_bytes(output) == 1474560

    def test_extract_written_bytes_large(self):
        output = (
            "Written: 29.8 GiB (32017047552 bytes) in 245 second(s).\n"
        )
        assert E01Writer._extract_written_bytes(output) == 32017047552

    def test_extract_written_bytes_missing(self):
        assert E01Writer._extract_written_bytes("no bytes info") == 0

    def test_progress_pattern(self):
        line = "Status: at 45%."
        match = E01_PROGRESS_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == "45"

    def test_progress_pattern_100(self):
        line = "Status: at 100%."
        match = E01_PROGRESS_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == "100"

    def test_progress_pattern_decimal(self):
        line = "Status: at 5.0%."
        match = E01_PROGRESS_PATTERN.search(line)
        assert match is not None
        assert match.group(1) == "5.0"

    def test_acquired_and_speed_patterns(self):
        s2 = (
            "acquired 188 MiB (197591040 bytes) of total 3.6 GiB (3926949888 bytes)"
        )
        m = E01_ACQUIRED_PATTERN.search(s2)
        assert m is not None
        assert int(m.group(1)) == 197591040
        assert int(m.group(2)) == 3926949888
        s3 = (
            "completion in 1 minute(s) and 15 second(s) with 47 MiB/s "
            "(49708226 bytes/second)"
        )
        m3 = E01_SPEED_PATTERN.search(s3)
        assert m3 is not None
        assert float(m3.group(2)) == 47.0
        assert int(m3.group(3)) == 49708226


class TestVerifyParsing:
    VERIFY_OUTPUT = (
        "Verify started at: Tue Jan 11 19:21:51 2011\n"
        "Status: at 100%.\n"
        "Verify completed at: Tue Jan 11 19:21:52 2011\n"
        "MD5 hash stored in file:\tae1ce8f5ac079d3ee93f97fe3792bda3\n"
        "MD5 hash calculated over data:\tae1ce8f5ac079d3ee93f97fe3792bda3\n"
        "SHA1 hash stored in file:\tab12cd34ef5678901234567890abcdef12345678\n"
        "SHA1 hash calculated over data:\tab12cd34ef5678901234567890abcdef12345678\n"
        "ewfverify: SUCCESS\n"
    )

    def test_stored_hash_pattern(self):
        matches = re.findall(EWFVERIFY_STORED_HASH_PATTERN, self.VERIFY_OUTPUT)
        assert len(matches) >= 1
        algos = [m[0] for m in matches]
        assert "MD5" in algos

    def test_computed_hash_pattern(self):
        matches = re.findall(EWFVERIFY_COMPUTED_HASH_PATTERN, self.VERIFY_OUTPUT)
        assert len(matches) >= 1

    def test_success_pattern(self):
        assert re.search(EWFVERIFY_SUCCESS_PATTERN, self.VERIFY_OUTPUT) is not None

    def test_failure_case(self):
        output = "ewfverify: FAILURE\n"
        assert re.search(EWFVERIFY_SUCCESS_PATTERN, output) is None


class TestCrAwareStreamReader:
    def test_carriage_return_splits_lines_like_ewfacquire(self):
        """ewfacquire が \\r で同一行上書きする場合でも readline より先に行が確定する"""

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_data(
                b"CopyStatus: at 1%.\rStatus: at 50%.\rStatus: at 100%.\r\n"
            )
            reader.feed_data(b"Acquiry completed at: Sun\n")
            reader.feed_eof()
            writer = E01Writer()
            lines = []
            await writer._read_stream_cr_aware(reader, lines, parse_progress=False)
            return lines

        lines = asyncio.run(run())
        assert lines == [
            "CopyStatus: at 1%.",
            "Status: at 50%.",
            "Status: at 100%.",
            "Acquiry completed at: Sun",
        ]
