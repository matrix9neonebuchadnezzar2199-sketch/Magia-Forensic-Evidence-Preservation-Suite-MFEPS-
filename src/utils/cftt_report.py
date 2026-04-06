"""
MFEPS — NIST CFTT テスト結果レポートジェネレータ
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.constants import APP_VERSION


@dataclass
class CfttTestResult:
    test_id: str
    requirement: str
    passed: bool
    detail: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CfttReportGenerator:
    def __init__(self) -> None:
        self._results: list[CfttTestResult] = []

    def add_result(self, result: CfttTestResult) -> None:
        self._results.append(result)

    def generate(self) -> dict[str, Any]:
        passed = sum(1 for r in self._results if r.passed)
        failed = sum(1 for r in self._results if not r.passed)
        return {
            "tool": "MFEPS",
            "version": APP_VERSION,
            "date": datetime.now(timezone.utc).isoformat(),
            "results": [
                {
                    "test_id": r.test_id,
                    "requirement": r.requirement,
                    "result": "PASS" if r.passed else "FAIL",
                    "detail": r.detail,
                    "timestamp": r.timestamp,
                }
                for r in self._results
            ],
            "summary": {
                "total": len(self._results),
                "passed": passed,
                "failed": failed,
            },
        }

    def export_json(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.generate(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
