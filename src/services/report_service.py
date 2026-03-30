"""
MFEPS v2.0 — 報告書生成サービス (PDF / HTML)
Jinja2 テンプレート + ReportLab PDF
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models.database import session_scope
from src.models.schema import ImagingJob, HashRecord, Case, EvidenceItem
from src.utils.config import get_config
from src.utils.constants import APP_VERSION

logger = logging.getLogger("mfeps.report_service")


def _register_pdf_japanese_font() -> str:
    """Windows 標準の日本語フォントを ReportLab に登録。失敗時は Helvetica。"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        try:
            pdfmetrics.getFont("MFEPSJP")
            return "MFEPSJP"
        except KeyError:
            pass

        windir = os.environ.get("WINDIR", r"C:\Windows")
        fonts_dir = Path(windir) / "Fonts"
        candidates = [
            ("msgothic.ttc", 0),
            ("YuGothM.ttc", 0),
            ("meiryo.ttc", 0),
            ("msgothic.ttf", None),
            ("meiryo.ttf", None),
        ]
        for fname, sub in candidates:
            p = fonts_dir / fname
            if not p.is_file():
                continue
            try:
                if sub is not None:
                    pdfmetrics.registerFont(
                        TTFont("MFEPSJP", str(p), subfontIndex=sub)
                    )
                else:
                    pdfmetrics.registerFont(TTFont("MFEPSJP", str(p)))
                return "MFEPSJP"
            except Exception:
                continue
        return "Helvetica"
    except Exception:
        return "Helvetica"


class ReportService:
    """報告書生成"""

    def generate_pdf(self, job_id: str) -> str:
        """PDF報告書を生成"""
        data = self._collect_report_data(job_id)
        if not data:
            raise ValueError(f"ジョブが見つかりません: {job_id}")

        config = get_config()
        output_dir = config.reports_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{data['case_number']}_{data['evidence_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = output_dir / filename

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            from reportlab.lib.colors import HexColor

            jp = _register_pdf_japanese_font()

            c = canvas.Canvas(str(output_path), pagesize=A4)
            width, height = A4

            # 表紙
            c.setFillColor(HexColor("#1A1A2E"))
            c.rect(0, 0, width, height, fill=1)

            c.setFillColor(HexColor("#FFFFFF"))
            c.setFont("Helvetica-Bold", 28)
            c.drawCentredString(width / 2, height - 150, "MFEPS")

            c.setFont("Helvetica", 14)
            c.drawCentredString(width / 2, height - 180,
                               "Forensic Evidence Preservation Suite")

            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 18)
            else:
                c.setFont(jp, 18)
            c.drawCentredString(width / 2, height - 250,
                               "デジタル証拠イメージング報告書")

            c.setFont(jp, 12)
            y = height - 320
            info_lines = [
                f"案件番号: {data['case_number']}",
                f"案件名: {data['case_name']}",
                f"証拠品番号: {data['evidence_number']}",
                f"鑑識者: {data['examiner_name']}",
                f"報告書生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"MFEPS v{APP_VERSION}",
            ]
            for line in info_lines:
                c.drawCentredString(width / 2, y, line)
                y -= 20

            c.showPage()

            # セクション: ハッシュ検証結果
            c.setFillColor(HexColor("#000000"))
            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 16)
            else:
                c.setFont(jp, 16)
            c.drawString(30, height - 50, "ハッシュ検証結果")

            y = height - 80
            c.setFont(jp, 10)

            for label, hashes in [("ソース", data.get("source_hashes", {})),
                                  ("イメージ", data.get("verify_hashes", {}))]:
                if jp == "Helvetica":
                    c.setFont("Helvetica-Bold", 12)
                else:
                    c.setFont(jp, 12)
                c.drawString(30, y, f"■ {label}")
                y -= 18

                c.setFont("Courier", 10)
                for algo in ["md5", "sha1", "sha256", "sha512"]:
                    val = hashes.get(algo) or "N/A"
                    c.drawString(50, y, f"{algo.upper().ljust(8)}: {val}")
                    y -= 14
                y -= 8

            # 照合結果
            match = data.get("match_result", "pending")
            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 14)
            else:
                c.setFont(jp, 14)
            if match == "matched":
                c.setFillColor(HexColor("#00E676"))
                c.drawString(30, y, "✅ 全ハッシュ一致: 完全性確認済み")
            else:
                c.setFillColor(HexColor("#FF5252"))
                c.drawString(30, y, "❌ ハッシュ不一致: 完全性に問題あり")

            c.setFillColor(HexColor("#000000"))
            y -= 40

            # 統計情報
            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 12)
            else:
                c.setFont(jp, 12)
            c.drawString(30, y, "■ 統計情報")
            y -= 18
            c.setFont(jp, 10)
            stats = [
                f"総バイト数: {data.get('total_bytes', 0):,} bytes",
                f"コピー済み: {data.get('copied_bytes', 0):,} bytes",
                f"所要時間: {data.get('elapsed_seconds', 0):.1f} 秒",
                f"平均速度: {data.get('avg_speed', 0):.1f} MiB/s",
                f"エラーセクタ: {data.get('error_count', 0)}",
            ]
            for s in stats:
                c.drawString(50, y, s)
                y -= 14

            # 書き込み保護方式
            y -= 30
            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 12)
            else:
                c.setFont(jp, 12)
            c.drawString(30, y, "■ 書き込み保護")
            y -= 18
            c.setFont(jp, 10)

            wb_method = data.get("write_block_method", "none")
            wb_labels = {
                "both": "ハードウェア + ソフトウェア（最高信頼性）",
                "hardware": "ハードウェアライトブロッカー",
                "software": "ソフトウェアのみ（レジストリ方式）",
                "none": "未使用",
            }
            c.drawString(50, y, f"方式: {wb_labels.get(wb_method, wb_method)}")
            y -= 14

            if wb_method == "software":
                c.setFillColor(HexColor("#FF9800"))
                c.drawString(50, y, "⚠ ソフトウェアライトブロックは法廷証拠として")
                y -= 14
                c.drawString(50, y, "  ハードウェア方式と同等の信頼性を保証しません。")
                y -= 14
                c.drawString(50, y, "  ハードウェアライトブロッカーとの併用を推奨します。")
                c.setFillColor(HexColor("#000000"))
                y -= 14
            elif wb_method == "none":
                c.setFillColor(HexColor("#FF5252"))
                c.drawString(50, y, "⚠ 書き込み保護が未使用です。証拠保全として不適切な可能性があります。")
                c.setFillColor(HexColor("#000000"))
                y -= 14

            c.showPage()
            c.save()

            logger.info(f"PDF 報告書生成: {output_path}")
            return str(output_path)

        except ImportError:
            logger.error("ReportLab が未インストールです")
            raise

    def generate_html(self, job_id: str) -> str:
        """HTML 報告書を生成"""
        data = self._collect_report_data(job_id)
        if not data:
            raise ValueError(f"ジョブが見つかりません: {job_id}")

        config = get_config()
        output_dir = config.reports_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{data['case_number']}_{data['evidence_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = output_dir / filename

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>MFEPS - デジタル証拠イメージング報告書</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
h1 {{ color: #6C63FF; border-bottom: 2px solid #6C63FF; padding-bottom: 10px; }}
h2 {{ color: #333; margin-top: 30px; }}
.hash {{ font-family: 'Consolas', monospace; background: #f5f5f5; padding: 2px 6px; }}
.match {{ color: #00C853; font-weight: bold; }}
.mismatch {{ color: #FF1744; font-weight: bold; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f0f0f0; }}
</style>
</head>
<body>
<h1>🔬 MFEPS — デジタル証拠イメージング報告書</h1>

<h2>案件概要</h2>
<table>
<tr><th>案件番号</th><td>{data['case_number']}</td></tr>
<tr><th>案件名</th><td>{data['case_name']}</td></tr>
<tr><th>鑑識者</th><td>{data['examiner_name']}</td></tr>
<tr><th>証拠品番号</th><td>{data['evidence_number']}</td></tr>
</table>

<h2>ハッシュ検証結果</h2>
<table>
<tr><th>アルゴリズム</th><th>ソース</th><th>イメージ</th><th>結果</th></tr>"""

        source_h = data.get("source_hashes", {})
        verify_h = data.get("verify_hashes", {})
        for algo in ["md5", "sha1", "sha256", "sha512"]:
            s = source_h.get(algo) or "N/A"
            v = verify_h.get(algo) or "N/A"
            match = "✅" if s == v and s != "N/A" else "❌"
            html += f'\n<tr><td>{algo.upper()}</td><td class="hash">{s}</td><td class="hash">{v}</td><td>{match}</td></tr>'

        match_result = data.get("match_result", "pending")
        match_class = "match" if match_result == "matched" else "mismatch"
        match_text = "全ハッシュ一致" if match_result == "matched" else "ハッシュ不一致"
        html += f"""
</table>
<p class="{match_class}">総合判定: {match_text}</p>

<h2>統計情報</h2>
<table>
<tr><th>総バイト数</th><td>{data.get('total_bytes', 0):,} bytes</td></tr>
<tr><th>所要時間</th><td>{data.get('elapsed_seconds', 0):.1f} 秒</td></tr>
<tr><th>平均速度</th><td>{data.get('avg_speed', 0):.1f} MiB/s</td></tr>
<tr><th>エラーセクタ</th><td>{data.get('error_count', 0)}</td></tr>
</table>
"""

        wb_method = data.get("write_block_method", "none")
        wb_labels = {
            "both": "ハードウェア + ソフトウェア（最高信頼性）",
            "hardware": "ハードウェアライトブロッカー",
            "software": "ソフトウェアのみ（レジストリ方式）",
            "none": "未使用",
        }
        wb_warning = ""
        if wb_method == "software":
            wb_warning = (
                '<p style="color: #FF9800;">⚠ ソフトウェアライトブロックは法廷証拠として'
                "ハードウェア方式と同等の信頼性を保証しません。"
                "ハードウェアライトブロッカーとの併用を推奨します。</p>"
            )
        elif wb_method == "none":
            wb_warning = (
                '<p style="color: #FF1744;">⚠ 書き込み保護が未使用です。'
                "証拠保全として不適切な可能性があります。</p>"
            )

        html += f"""
<h2>書き込み保護</h2>
<table>
<tr><th>保護方式</th><td>{wb_labels.get(wb_method, wb_method)}</td></tr>
</table>
{wb_warning}
"""

        html += f"""
<hr>
<p><small>本報告書は MFEPS v{APP_VERSION} により自動生成されました。</small></p>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML 報告書生成: {output_path}")
        return str(output_path)

    def _collect_report_data(self, job_id: str) -> Optional[dict]:
        """報告書用データをDBから収集"""
        with session_scope() as session:
            job = session.get(ImagingJob, job_id)
            if not job:
                return None

            evidence = (
                session.get(EvidenceItem, job.evidence_id)
                if job.evidence_id
                else None
            )
            case = (
                session.get(Case, evidence.case_id)
                if evidence and evidence.case_id
                else None
            )

            source_hash = session.query(HashRecord).filter_by(
                job_id=job_id, target="source"
            ).first()
            verify_hash = session.query(HashRecord).filter_by(
                job_id=job_id, target="verify"
            ).first()

            def _hash_fields(hr: Optional[HashRecord]) -> dict:
                if not hr:
                    return {
                        "md5": "",
                        "sha1": "",
                        "sha256": "",
                        "sha512": "",
                    }
                return {
                    "md5": hr.md5 or "",
                    "sha1": hr.sha1 or "",
                    "sha256": hr.sha256 or "",
                    "sha512": getattr(hr, "sha512", None) or "",
                }

            return {
                "case_number": case.case_number if case else "N/A",
                "case_name": case.case_name if case else "N/A",
                "examiner_name": case.examiner_name if case else "N/A",
                "evidence_number": evidence.evidence_number if evidence else "N/A",
                "source_hashes": _hash_fields(source_hash),
                "verify_hashes": _hash_fields(verify_hash),
                "match_result": (
                    verify_hash.match_result if verify_hash else "pending"
                ),
                "total_bytes": job.total_bytes,
                "copied_bytes": job.copied_bytes,
                "elapsed_seconds": job.elapsed_seconds,
                "avg_speed": job.avg_speed_mbps,
                "error_count": job.error_count,
                "write_block_method": job.write_block_method or "none",
            }
