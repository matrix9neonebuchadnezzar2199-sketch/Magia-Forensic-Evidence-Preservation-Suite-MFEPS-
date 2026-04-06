"""CFTT テスト結果レポート生成"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.cftt_report import CfttReportGenerator, CfttTestResult

pytestmark = pytest.mark.cftt


class TestCfttReport:
    def test_all_pass_report(self):
        gen = CfttReportGenerator()
        gen.add_result(
            CfttTestResult(
                test_id="DI-RM-01",
                requirement="No source write",
                passed=True,
                detail="SHA-256 unchanged",
            )
        )
        report = gen.generate()
        assert report["summary"]["total"] == 1
        assert report["summary"]["passed"] == 1

    def test_partial_fail_report(self, tmp_path: Path):
        gen = CfttReportGenerator()
        gen.add_result(
            CfttTestResult(
                test_id="DI-RM-01",
                requirement="No source write",
                passed=True,
                detail="OK",
            )
        )
        gen.add_result(
            CfttTestResult(
                test_id="DI-RM-03",
                requirement="Hash match",
                passed=False,
                detail="MD5 mismatch",
            )
        )
        out = tmp_path / "cftt.json"
        gen.export_json(out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["summary"]["failed"] == 1
