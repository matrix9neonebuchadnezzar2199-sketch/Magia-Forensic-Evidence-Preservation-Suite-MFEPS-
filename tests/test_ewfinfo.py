"""ewfinfo 出力パーサーのユニットテスト"""

from src.core.e01_writer import E01Writer


class TestEwfinfoParser:
    """Test ewfinfo output parsing."""

    SAMPLE_OUTPUT = """ewfinfo 20230405

Acquiry information:
\tCase number:\tCASE-001
\tEvidence number:\tEV-001
\tExaminer name:\tTest Examiner
\tAcquiry date:\tMar 31 2026 10:00:00

Media information:
\tMedia type:\tfixed
\tMedia size:\t3.9 GiB (3926950076 bytes)
\tBytes per sector:\t512

Digest hash information:
\tMD5:\tfe00fe0ce5792f54c069b2917c6082cf

EWF information:
\tFile format:\tEnCase 6 (.E01)
\tCompression method:\tdeflate
\tNumber of segments:\t3
"""

    def test_parse_sections(self):
        result = E01Writer._parse_ewfinfo_output(self.SAMPLE_OUTPUT)
        assert "Acquiry information" in result
        assert "Media information" in result
        assert "Digest hash information" in result
        assert "EWF information" in result

    def test_acquiry_fields(self):
        result = E01Writer._parse_ewfinfo_output(self.SAMPLE_OUTPUT)
        assert result["Acquiry information"]["Case number"] == "CASE-001"
        assert result["Acquiry information"]["Examiner name"] == "Test Examiner"

    def test_media_size(self):
        result = E01Writer._parse_ewfinfo_output(self.SAMPLE_OUTPUT)
        assert "3926950076" in result["Media information"]["Media size"]

    def test_digest_md5(self):
        result = E01Writer._parse_ewfinfo_output(self.SAMPLE_OUTPUT)
        assert (
            result["Digest hash information"]["MD5"]
            == "fe00fe0ce5792f54c069b2917c6082cf"
        )

    def test_empty_output(self):
        result = E01Writer._parse_ewfinfo_output("")
        assert result == {}

    def test_no_hash_section(self):
        partial = "Media information:\n\tMedia type:\tfixed\n"
        result = E01Writer._parse_ewfinfo_output(partial)
        assert "Digest hash information" not in result
        assert result["Media information"]["Media type"] == "fixed"
