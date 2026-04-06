"""
MFEPS v2.1.0 — 報告書生成サービス (PDF / HTML)
Jinja2 テンプレート + ReportLab PDF
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.database import session_scope
from src.models.schema import ImagingJob, HashRecord, Case, EvidenceItem
from src.services.imaging_service import get_imaging_service
from src.utils.constants import APP_VERSION
from src.utils.reports_paths import case_reports_dir

logger = logging.getLogger("mfeps.report_service")


def _examiner_label(case: Optional[Case]) -> str:
    if not case:
        return "N/A"
    t = (case.examiner_name or "").strip()
    return t or "未記入"


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

        output_dir = case_reports_dir(
            data["case_name"], case_number=data["case_number"]
        )

        filename = f"{data['case_number']}_{data['evidence_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = output_dir / filename

        try:
            from reportlab.lib.pagesizes import A4
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
                for algo in ["md5", "sha256", "sha512"]:
                    val = (hashes.get(algo) or "").strip()
                    if not val:
                        continue
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

            cap_notes = data.get("capacity_notes", "")
            if cap_notes and "capacity_source" in cap_notes:
                try:
                    for line in reversed(cap_notes.split("\n")):
                        line = line.strip()
                        if line.startswith("{") and "capacity_source" in line:
                            diag = json.loads(line)
                            declared = diag.get("declared_capacity_bytes", 0)
                            actual = diag.get("actual_read_bytes", 0)
                            if declared != actual and declared > 0 and actual > 0:
                                diff = declared - actual
                                y -= 14
                                c.drawString(
                                    50,
                                    y,
                                    f"メディア申告容量: {declared:,} bytes "
                                    f"(実読取との差分: {diff:,} bytes)",
                                )
                            break
                except Exception:
                    pass

            if data.get("output_format") == "e01":
                y -= 20
                if jp == "Helvetica":
                    c.setFont("Helvetica-Bold", 12)
                else:
                    c.setFont(jp, 12)
                c.drawString(30, y, "■ E01 取得情報")
                y -= 18
                c.setFont(jp, 9)
                e01_lines = [
                    f"EWF: {data.get('e01_ewf_format', 'N/A')}",
                    f"圧縮: {data.get('e01_compression', 'N/A')}",
                    f"セグメント: {data.get('e01_segment_size_bytes', 0):,} bytes × "
                    f"{data.get('e01_segment_count', 0)}",
                    f"ewfacquire: {data.get('e01_ewfacquire_version', 'N/A')}",
                ]
                for line in e01_lines:
                    c.drawString(50, y, line)
                    y -= 12
                cmd_txt = data.get("e01_command_line", "") or "N/A"
                if len(cmd_txt) > 120:
                    cmd_txt = cmd_txt[:117] + "..."
                c.drawString(50, y, f"cmd: {cmd_txt}")
                y -= 14

                ewf = data.get("ewfinfo")
                if ewf and ewf.get("success") and ewf.get("sections"):
                    y -= 16
                    if jp == "Helvetica":
                        c.setFont("Helvetica-Bold", 12)
                    else:
                        c.setFont(jp, 12)
                    c.drawString(30, y, "■ E01 メタデータ (ewfinfo)")
                    y -= 16
                    c.setFont(jp, 8)
                    ver = (ewf.get("version") or "").strip()
                    if ver:
                        c.drawString(50, y, f"ewfinfo: {ver}")
                        y -= 11
                    for sec_name, kvs in ewf["sections"].items():
                        c.drawString(50, y, f"[{sec_name}]")
                        y -= 10
                        for k, v in kvs.items():
                            line = f"  {k}: {v}"
                            if len(line) > 110:
                                line = line[:107] + "..."
                            c.drawString(50, y, line)
                            y -= 9
                            if y < 40:
                                c.showPage()
                                y = A4[1] - 40
                                c.setFont(jp, 8)

            rfc_pdf = data.get("rfc3161") or {}
            y -= 24
            if jp == "Helvetica":
                c.setFont("Helvetica-Bold", 12)
            else:
                c.setFont(jp, 12)
            c.drawString(30, y, "■ RFC3161 タイムスタンプ")
            y -= 16
            c.setFont(jp, 9)
            if rfc_pdf.get("has_timestamp"):
                c.drawString(50, y, "状態: 取得済み")
                y -= 12
                c.drawString(
                    50,
                    y,
                    f"TSA: {(rfc_pdf.get('tsa_url') or '')[:90]}",
                )
                y -= 12
            else:
                c.drawString(50, y, "記録なし（設定無効または未取得）")
                y -= 12

            oi_pdf = data.get("optical_info")
            if oi_pdf:
                y -= 8
                if jp == "Helvetica":
                    c.setFont("Helvetica-Bold", 12)
                else:
                    c.setFont(jp, 12)
                c.drawString(30, y, "■ 光学メディア情報")
                y -= 16
                c.setFont(jp, 9)
                cap_b = int(oi_pdf.get("capacity_bytes") or 0)
                opt_lines = [
                    f"メディア種別: {oi_pdf.get('media_type', 'N/A')}",
                    f"ファイルシステム: {oi_pdf.get('file_system', 'N/A')}",
                    f"セクタサイズ: {oi_pdf.get('sector_size', 'N/A')} bytes",
                    f"容量: {cap_b:,} bytes",
                    f"容量算出: {oi_pdf.get('capacity_source', 'N/A')}",
                    f"トラック数: {oi_pdf.get('track_count', 0)}",
                ]
                for line in opt_lines:
                    c.drawString(50, y, line[:110])
                    y -= 11
                    if y < 50:
                        c.showPage()
                        y = A4[1] - 50
                        c.setFont(jp, 9)

            cg_t_pdf = data.get("copy_guard_type") or ""
            cg_d_pdf = data.get("copy_guard_detail") or ""
            if cg_t_pdf or cg_d_pdf:
                y -= 8
                if jp == "Helvetica":
                    c.setFont("Helvetica-Bold", 12)
                else:
                    c.setFont(jp, 12)
                c.drawString(30, y, "■ コピーガード分析")
                y -= 14
                c.setFont(jp, 9)
                if cg_t_pdf:
                    c.drawString(50, y, f"検出: {cg_t_pdf[:100]}")
                    y -= 11
                if cg_d_pdf:
                    snippet = (cg_d_pdf[:200] + "...") if len(cg_d_pdf) > 200 else cg_d_pdf
                    c.drawString(50, y, f"詳細: {snippet[:100]}")
                    y -= 11

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

        output_dir = case_reports_dir(
            data["case_name"], case_number=data["case_number"]
        )

        filename = f"{data['case_number']}_{data['evidence_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = output_dir / filename

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>MFEPS - デジタル証拠イメージング報告書</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
h1 {{ color: #f54e00; border-bottom: 2px solid #f54e00; padding-bottom: 10px; }}
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
        for algo in ["md5", "sha256", "sha512"]:
            s = (source_h.get(algo) or "").strip()
            v = (verify_h.get(algo) or "").strip()
            if not s and not v:
                continue
            ds = s or "N/A"
            dv = v or "N/A"
            match = "✅" if s and v and s == v else "❌"
            html += f'\n<tr><td>{algo.upper()}</td><td class="hash">{ds}</td><td class="hash">{dv}</td><td>{match}</td></tr>'

        match_result = data.get("match_result", "pending")
        match_class = "match" if match_result == "matched" else "mismatch"
        match_text = "全ハッシュ一致" if match_result == "matched" else "ハッシュ不一致"

        cap_notes_html = ""
        cap_notes = data.get("capacity_notes", "")
        if cap_notes and "capacity_source" in cap_notes:
            try:
                for line in reversed(cap_notes.split("\n")):
                    line = line.strip()
                    if line.startswith("{") and "capacity_source" in line:
                        diag = json.loads(line)
                        declared = diag.get("declared_capacity_bytes", 0)
                        actual = diag.get("actual_read_bytes", 0)
                        if declared != actual and declared > 0 and actual > 0:
                            diff = declared - actual
                            cap_notes_html = (
                                f'<tr><th>メディア申告容量</th>'
                                f"<td>{declared:,} bytes "
                                f"(実読取との差分: {diff:,} bytes)</td></tr>"
                            )
                        break
            except Exception:
                pass

        html += f"""
</table>
<p class="{match_class}">総合判定: {match_text}</p>

<h2>統計情報</h2>
<table>
<tr><th>総バイト数</th><td>{data.get('total_bytes', 0):,} bytes</td></tr>
<tr><th>所要時間</th><td>{data.get('elapsed_seconds', 0):.1f} 秒</td></tr>
<tr><th>平均速度</th><td>{data.get('avg_speed', 0):.1f} MiB/s</td></tr>
<tr><th>エラーセクタ</th><td>{data.get('error_count', 0)}</td></tr>
{cap_notes_html}
</table>
"""

        e01_section = ""
        if data.get("output_format") == "e01":
            e01_section = f"""
<h2>E01 取得情報</h2>
<table>
<tr><th>出力形式</th><td>E01 (Expert Witness Compression Format)</td></tr>
<tr><th>EWF フォーマット</th><td>{data.get('e01_ewf_format', 'N/A')}</td></tr>
<tr><th>圧縮</th><td>{data.get('e01_compression', 'N/A')}</td></tr>
<tr><th>セグメントサイズ</th><td>{data.get('e01_segment_size_bytes', 0):,} bytes</td></tr>
<tr><th>セグメント数</th><td>{data.get('e01_segment_count', 0)}</td></tr>
<tr><th>使用ツール</th><td>{data.get('e01_ewfacquire_version', 'N/A')}</td></tr>
<tr><th>実行コマンド</th><td><code style="word-break:break-all;">{data.get('e01_command_line', 'N/A')}</code></td></tr>
</table>
"""
        ewfinfo_section = ""
        ewf = data.get("ewfinfo")
        if ewf and ewf.get("success") and ewf.get("sections"):
            ver_html = ""
            v = (ewf.get("version") or "").strip()
            if v:
                ver_html = f"<p><small>ewfinfo バージョン: {v}</small></p>"
            rows = []
            for sec_name, kvs in ewf["sections"].items():
                rows.append(
                    f"<tr><th colspan='2'>{sec_name}</th></tr>"
                )
                for k, val in kvs.items():
                    esc_k = (
                        str(k).replace("&", "&amp;")
                        .replace("<", "&lt;").replace(">", "&gt;")
                    )
                    esc_v = (
                        str(val).replace("&", "&amp;")
                        .replace("<", "&lt;").replace(">", "&gt;")
                    )
                    rows.append(
                        f"<tr><td>{esc_k}</td><td>{esc_v}</td></tr>"
                    )
            ewfinfo_section = (
                "<h2>E01 メタデータ (ewfinfo)</h2>"
                f"{ver_html}"
                "<table>"
                + "".join(rows)
                + "</table>"
            )
        html += e01_section + ewfinfo_section

        rfc_d = data.get("rfc3161") or {}
        if rfc_d.get("has_timestamp"):
            _tu = (rfc_d.get("tsa_url") or "").replace("&", "&amp;")
            html += f"""
<h2>RFC3161 タイムスタンプ</h2>
<table>
<tr><th>状態</th><td>取得済み</td></tr>
<tr><th>TSA URL</th><td>{_tu}</td></tr>
</table>
"""
        else:
            html += """
<h2>RFC3161 タイムスタンプ</h2>
<p>記録なし（設定無効、または未取得）</p>
"""

        oi = data.get("optical_info")
        if oi:
            html += f"""
<h2>光学メディア情報</h2>
<table>
<tr><th>メディア種別</th><td>{oi.get("media_type", "N/A")}</td></tr>
<tr><th>ファイルシステム</th><td>{oi.get("file_system", "N/A")}</td></tr>
<tr><th>セクタサイズ</th><td>{oi.get("sector_size", "N/A")} bytes</td></tr>
<tr><th>容量</th><td>{oi.get("capacity_bytes", 0):,} bytes</td></tr>
<tr><th>容量算出</th><td>{oi.get("capacity_source", "N/A")}</td></tr>
<tr><th>トラック数</th><td>{oi.get("track_count", 0)}</td></tr>
</table>
"""

        _cgt = data.get("copy_guard_type") or ""
        _cgd = data.get("copy_guard_detail") or ""
        if _cgt or _cgd:
            html += "<h2>コピーガード分析</h2><table>"
            if _cgt:
                html += f"<tr><th>検出タイプ</th><td>{_cgt}</td></tr>"
            if _cgd:
                esc = (
                    _cgd.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                html += (
                    f"<tr><th>詳細</th><td><pre style='white-space:pre-wrap'>"
                    f"{esc[:2000]}</pre></td></tr>"
                )
            html += "</table>"

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
                        "sha256": "",
                        "sha512": "",
                    }
                return {
                    "md5": hr.md5 or "",
                    "sha256": hr.sha256 or "",
                    "sha512": getattr(hr, "sha512", None) or "",
                }

            data = {
                "case_number": case.case_number if case else "N/A",
                "case_name": case.case_name if case else "N/A",
                "examiner_name": _examiner_label(case),
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
                "output_format": job.output_format or "raw",
                "e01_compression": getattr(job, "e01_compression", None) or "",
                "e01_segment_size_bytes": getattr(
                    job, "e01_segment_size_bytes", None
                )
                or 0,
                "e01_ewf_format": getattr(job, "e01_ewf_format", None) or "",
                "e01_examiner_name": getattr(job, "e01_examiner_name", None) or "",
                "e01_segment_count": getattr(job, "e01_segment_count", None) or 0,
                "e01_ewfacquire_version": getattr(
                    job, "e01_ewfacquire_version", None
                )
                or "",
                "e01_command_line": getattr(job, "e01_command_line", None) or "",
                "capacity_notes": job.notes or "",
            }

            optical_info = None
            for line in (job.notes or "").split("\n"):
                ln = line.strip()
                if not ln.startswith("{"):
                    continue
                if '"media_type"' not in ln or '"file_system"' not in ln:
                    continue
                try:
                    j = json.loads(ln)
                    if isinstance(j, dict) and j.get("media_type"):
                        optical_info = j
                        break
                except Exception:
                    continue

            data["optical_info"] = optical_info
            data["rfc3161"] = {
                "has_timestamp": bool(
                    source_hash and getattr(source_hash, "rfc3161_token", None)
                ),
                "tsa_url": (source_hash.rfc3161_tsa_url or "")
                if source_hash
                else "",
            }
            data["copy_guard_type"] = getattr(job, "copy_guard_type", None) or ""
            data["copy_guard_detail"] = (
                getattr(job, "copy_guard_detail", None) or ""
            )

        info = get_imaging_service().get_e01_info(job_id)
        data["ewfinfo"] = None
        if info and info.success:
            data["ewfinfo"] = {
                "success": True,
                "sections": info.sections,
                "version": info.ewfinfo_version or "",
            }
        return data
