"""
MFEPS v2.1.0 — E01 出力ラッパー (ewfacquire / ewfverify subprocess)

libewf の ewfacquire.exe を subprocess で制御し、
E01 (Expert Witness Compression Format) でのイメージ取得を行う。

責務:
  1. ewfacquire / ewfverify の存在・バージョン確認
  2. コマンドライン組み立て（公式 CLI 準拠）
  3. subprocess 実行 + stdout リアルタイムパース（進捗抽出）
  4. 出力 E01 セグメントファイルの列挙
  5. ewfverify による検証
  6. キャンセル（プロセス停止）
"""
import asyncio
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.utils.config import get_config
from src.utils.incomplete_file_detector import detect_incomplete_files
from src.utils.storage_helpers import get_storage_value
from src.utils.constants import (
    E01_DEFAULT_COMPRESSION_METHOD,
    E01_DEFAULT_COMPRESSION_LEVEL,
    E01_DEFAULT_SECTORS_PER_CHUNK,
    E01_DEFAULT_EWF_FORMAT,
    E01_DEFAULT_READ_ERROR_RETRIES,
    E01_DEFAULT_SEGMENT_SIZE_BYTES,
    E01_PROGRESS_PATTERN,
    E01_ACQUIRED_PATTERN,
    E01_SPEED_PATTERN,
    E01_HASH_PATTERN,
    E01_WRITTEN_PATTERN,
    EWFVERIFY_STORED_HASH_PATTERN,
    EWFVERIFY_COMPUTED_HASH_PATTERN,
    EWFVERIFY_SUCCESS_PATTERN,
    EWFINFO_KV_PATTERN,
    EWFINFO_SECTION_PATTERN,
)

logger = logging.getLogger("mfeps.e01_writer")

_CTRL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_EWF_METADATA_LEN = 200


def _sanitize_ewf_metadata(value: str, field_name: str = "") -> str:
    """ewfacquire メタデータ引数用: 制御文字除去 + 長さ上限"""
    cleaned = _CTRL_CHAR_RE.sub("", value or "").strip()
    if len(cleaned) > _MAX_EWF_METADATA_LEN:
        logger.warning(
            "E01 メタデータ %s を %d→%d 文字に切り詰めました",
            field_name or "(field)",
            len(cleaned),
            _MAX_EWF_METADATA_LEN,
        )
        cleaned = cleaned[:_MAX_EWF_METADATA_LEN]
    return cleaned


@dataclass
class E01Params:
    """E01 取得パラメータ"""

    source_path: str
    output_dir: str
    output_basename: str = "image"

    case_number: str = ""
    evidence_number: str = ""
    examiner_name: str = ""
    description: str = ""
    notes: str = ""

    compression_method: str = E01_DEFAULT_COMPRESSION_METHOD
    compression_level: str = E01_DEFAULT_COMPRESSION_LEVEL
    segment_size_bytes: int = E01_DEFAULT_SEGMENT_SIZE_BYTES
    sectors_per_chunk: int = E01_DEFAULT_SECTORS_PER_CHUNK
    ewf_format: str = E01_DEFAULT_EWF_FORMAT
    read_error_retries: int = E01_DEFAULT_READ_ERROR_RETRIES
    zero_on_error: bool = True

    media_type: str = "removable"
    media_flags: str = "physical"

    calculate_sha256: bool = True


@dataclass
class E01Result:
    """E01 取得結果"""

    success: bool = False
    output_files: list[str] = field(default_factory=list)
    segment_count: int = 0
    total_bytes: int = 0
    acquired_bytes: int = 0
    md5: str = ""
    sha256: str = ""
    elapsed_seconds: float = 0.0
    ewfacquire_return_code: int = -1
    ewfacquire_stdout: str = ""
    ewfacquire_stderr: str = ""
    ewfacquire_version: str = ""
    command_line: str = ""
    log_file_path: str = ""
    error_code: str = ""
    error_message: str = ""
    incomplete_files: list[str] = field(default_factory=list)
    incomplete_total_bytes: int = 0
    incomplete_file_records: list[dict] = field(default_factory=list)


@dataclass
class E01VerifyResult:
    """E01 検証結果"""

    verified: bool = False
    stored_hashes: dict = field(default_factory=dict)
    computed_hashes: dict = field(default_factory=dict)
    return_code: int = -1
    output: str = ""  # stdout + stderr（結合）
    log_file_path: str = ""
    skipped: bool = False
    skip_reason: str = ""
    error_message: str = ""


@dataclass
class E01InfoResult:
    """ewfinfo のパース結果"""

    success: bool = False
    sections: dict[str, dict[str, str]] = field(default_factory=dict)
    raw_output: str = ""
    return_code: int = -1
    error_message: str = ""
    ewfinfo_version: str = ""

    @property
    def media_type(self) -> str:
        return self.sections.get("Media information", {}).get("Media type", "")

    @property
    def media_size(self) -> str:
        return self.sections.get("Media information", {}).get("Media size", "")

    @property
    def digest_md5(self) -> str:
        return self.sections.get("Digest hash information", {}).get("MD5", "")

    @property
    def digest_sha256(self) -> str:
        return self.sections.get("Digest hash information", {}).get("SHA256", "")

    @property
    def case_number(self) -> str:
        return self.sections.get("Acquiry information", {}).get("Case number", "")

    @property
    def evidence_number(self) -> str:
        return self.sections.get("Acquiry information", {}).get("Evidence number", "")

    @property
    def examiner_name(self) -> str:
        return self.sections.get("Acquiry information", {}).get("Examiner name", "")

    @property
    def acquiry_date(self) -> str:
        return self.sections.get("Acquiry information", {}).get("Acquiry date", "")

    @property
    def compression_method(self) -> str:
        return self.sections.get("EWF information", {}).get("Compression method", "")

    @property
    def segments(self) -> str:
        return self.sections.get("EWF information", {}).get("Number of segments", "")


class E01Writer:
    """ewfacquire.exe を subprocess で呼び出し E01 イメージを生成する。"""

    def __init__(self) -> None:
        self._cancel_requested = False
        self._process: Optional[asyncio.subprocess.Process] = None
        self._progress_callback: Optional[Callable] = None
        self._current_progress: dict = {
            "status": "idle",
            "percent": 0.0,
            "raw_line": "",
            "acquired_bytes": 0,
            "total_bytes": 0,
            "remaining": "",
            "speed_display": "",
            "speed_bytes": 0,
        }

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    def get_progress(self) -> dict:
        return self._current_progress.copy()

    @staticmethod
    def _resolve_stored_tool_path(stored: str) -> str | None:
        """設定ストレージのパスを base_dir 基準で解決。実在ファイルなら絶対パスを返す。"""
        if not (stored or "").strip():
            return None
        cfg = get_config()
        p = Path(stored.strip())
        if not p.is_absolute():
            p = (cfg.base_dir / p).resolve()
        else:
            p = p.resolve()
        if p.is_file():
            return str(p)
        return None

    @staticmethod
    def _resolve_ewfacquire_path() -> str:
        """storage（実在時）> 設定 / 自動 libs 検索"""
        raw = (get_storage_value("ewfacquire_path") or "").strip()
        resolved = E01Writer._resolve_stored_tool_path(raw)
        if resolved:
            return resolved
        return get_config().resolve_ewfacquire_path()

    @staticmethod
    def _resolve_ewfverify_path() -> str:
        """ewfverify（storage 優先、その後設定 / 自動 libs 検索）"""
        raw = (get_storage_value("ewfverify_path") or "").strip()
        resolved = E01Writer._resolve_stored_tool_path(raw)
        if resolved:
            return resolved
        return get_config().resolve_ewfverify_path()

    @staticmethod
    def _resolve_ewfinfo_path() -> str:
        """ewfinfo（storage 優先、その後設定 / 自動 libs 検索）"""
        raw = (get_storage_value("ewfinfo_path") or "").strip()
        resolved = E01Writer._resolve_stored_tool_path(raw)
        if resolved:
            return resolved
        return get_config().resolve_ewfinfo_path()

    @staticmethod
    def check_available() -> dict:
        acq_path = E01Writer._resolve_ewfacquire_path()
        ver_path = E01Writer._resolve_ewfverify_path()
        result = {
            "ewfacquire_available": False,
            "ewfverify_available": False,
            "ewfacquire_path": acq_path,
            "ewfverify_path": ver_path,
            "ewfacquire_version": "",
            "ewfverify_version": "",
        }

        if acq_path and Path(acq_path).is_file():
            try:
                proc = subprocess.run(
                    [acq_path, "-V"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                result["ewfacquire_available"] = True
                result["ewfacquire_version"] = (proc.stdout or proc.stderr or "").strip()
            except Exception as e:
                logger.debug("ewfacquire -V 失敗: %s", e)

        if ver_path and Path(ver_path).is_file():
            try:
                proc = subprocess.run(
                    [ver_path, "-V"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                result["ewfverify_available"] = True
                result["ewfverify_version"] = (proc.stdout or proc.stderr or "").strip()
            except Exception as e:
                logger.debug("ewfverify -V 失敗: %s", e)

        return result

    @staticmethod
    def check_available_detail() -> dict:
        """設定画面用: 利用可否 + ステータス文字列 + 診断メッセージ"""
        config = get_config()
        base = E01Writer.check_available()
        diag: list[str] = []

        stored_acq = (get_storage_value("ewfacquire_path") or "").strip()
        stored_ver = (get_storage_value("ewfverify_path") or "").strip()

        cfg_acq = (config.ewfacquire_path or "").strip()
        cfg_ver = (config.ewfverify_path or "").strip()
        acq_resolved = base.get("ewfacquire_path") or ""
        ver_resolved = base.get("ewfverify_path") or ""

        # ewfacquire
        if base["ewfacquire_available"]:
            base["ewfacquire_status"] = "利用可能"
        elif not acq_resolved:
            base["ewfacquire_status"] = "未設定"
            diag.append(
                "ewfacquire が見つかりません。"
                "プロジェクトの libs/ewfacquire.exe を置くか、"
                ".env の EWFACQUIRE_PATH または設定画面でパスを指定してください。"
            )
        elif acq_resolved and not Path(acq_resolved).is_file():
            base["ewfacquire_status"] = "ファイル未検出"
            diag.append(f"指定パスにファイルが存在しません: {acq_resolved}")
        else:
            base["ewfacquire_status"] = "実行エラー"
            diag.append(
                "ewfacquire.exe は存在しますが -V の実行に失敗しました。"
                "DLL 不足やアーキテクチャ不一致の可能性があります。"
            )

        # ewfverify
        if base["ewfverify_available"]:
            base["ewfverify_status"] = "利用可能"
        elif not ver_resolved:
            base["ewfverify_status"] = "未設定（検証スキップ）"
        elif ver_resolved and not Path(ver_resolved).is_file():
            base["ewfverify_status"] = "ファイル未検出"
            diag.append(f"指定パスにファイルが存在しません: {ver_resolved}")
        else:
            base["ewfverify_status"] = "実行エラー"

        base["diagnostics"] = diag
        return base

    def build_command(self, params: E01Params) -> tuple[list[str], str]:
        ewfacquire_path = E01Writer._resolve_ewfacquire_path()

        target_path = str(Path(params.output_dir) / params.output_basename)
        log_path = str(
            Path(params.output_dir) / f"{params.output_basename}_ewfacquire.log"
        )
        compression_value = f"{params.compression_method}:{params.compression_level}"

        cmd: list[str] = [
            ewfacquire_path,
            "-t",
            target_path,
        ]
        cn = _sanitize_ewf_metadata(params.case_number or "", "case_number")
        if cn:
            cmd.extend(["-C", cn])
        desc = _sanitize_ewf_metadata(params.description or "", "description")
        if desc:
            cmd.extend(["-D", desc])
        exn = _sanitize_ewf_metadata(params.examiner_name or "", "examiner_name")
        if exn:
            cmd.extend(["-e", exn])
        evn = _sanitize_ewf_metadata(params.evidence_number or "", "evidence_number")
        if evn:
            cmd.extend(["-E", evn])
        nt = _sanitize_ewf_metadata(params.notes or "", "notes")
        if nt:
            cmd.extend(["-N", nt])
        cmd.extend(
            [
                "-f",
                params.ewf_format,
                "-c",
                compression_value,
                "-S",
                str(params.segment_size_bytes),
                "-b",
                str(params.sectors_per_chunk),
                "-m",
                params.media_type,
                "-M",
                params.media_flags,
                "-r",
                str(params.read_error_retries),
                "-l",
                log_path,
                "-u",
            ]
        )

        if params.zero_on_error:
            cmd.append("-w")

        if params.calculate_sha256:
            cmd.extend(["-d", "sha256"])

        cmd.append(params.source_path)

        return cmd, log_path

    @staticmethod
    def _attach_e01_incomplete_files(result: E01Result, params: E01Params) -> None:
        """成功以外のとき、出力先に残ったセグメント・ログを列挙する（削除はしない）。"""
        if result.success:
            return
        patterns = [
            f"{params.output_basename}.E*",
            f"{params.output_basename}.e*",
            f"{params.output_basename}_ewfacquire.log",
        ]
        entries = detect_incomplete_files(params.output_dir, patterns)
        result.incomplete_file_records = entries
        result.incomplete_files = [e["path"] for e in entries]
        result.incomplete_total_bytes = sum(e["size_bytes"] for e in entries)

    async def acquire(self, params: E01Params) -> E01Result:
        result = E01Result()
        self._cancel_requested = False

        availability = self.check_available()
        if not availability["ewfacquire_available"]:
            result.error_code = "E7001"
            acq = E01Writer._resolve_ewfacquire_path()
            result.error_message = (
                f"ewfacquire.exe が利用できません: {acq or '(未設定)'}"
            )
            logger.error(result.error_message)
            E01Writer._attach_e01_incomplete_files(result, params)
            return result

        result.ewfacquire_version = availability["ewfacquire_version"]

        cmd, log_path = self.build_command(params)
        result.command_line = " ".join(cmd)
        result.log_file_path = log_path
        logger.info("E01 取得コマンド: %s", result.command_line)

        Path(params.output_dir).mkdir(parents=True, exist_ok=True)

        start_time = time.monotonic()
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **self._subprocess_kwargs(),
            )

            stdout_task = asyncio.create_task(
                self._read_stream_cr_aware(
                    self._process.stdout, stdout_lines, parse_progress=True
                )
            )
            stderr_task = asyncio.create_task(
                self._read_stream_cr_aware(self._process.stderr, stderr_lines)
            )

            await asyncio.gather(stdout_task, stderr_task)

            return_code = await self._process.wait()

            # ewfacquire は最後の Status を 100% 未満で出さず Acquiry completed に移るため、
            # 完了直後に UI を 100% へ。バーは copied/total 比なので total に揃える。
            if self._progress_callback and not self._cancel_requested:
                self._current_progress["percent"] = 100.0
                self._current_progress["status"] = "finalizing"
                tb = int(self._current_progress.get("total_bytes") or 0)
                if tb > 0:
                    self._current_progress["acquired_bytes"] = tb
                self._progress_callback(dict(self._current_progress))

            elapsed = time.monotonic() - start_time
            result.elapsed_seconds = round(elapsed, 2)
            result.ewfacquire_return_code = return_code
            result.ewfacquire_stdout = "\n".join(stdout_lines)
            result.ewfacquire_stderr = "\n".join(stderr_lines)

            if self._cancel_requested:
                result.error_code = "E3006"
                result.error_message = "ユーザーによりキャンセルされました"
                logger.info("E01 取得キャンセル完了")
                return result

            if return_code != 0:
                result.error_code = "E7002"
                result.error_message = (
                    f"ewfacquire 異常終了 (code={return_code}): "
                    f"{result.ewfacquire_stderr[:500]}"
                )
                logger.error(result.error_message)
                return result

            out_dir = Path(params.output_dir)
            result.output_files = sorted(
                str(p) for p in out_dir.glob(f"{params.output_basename}.E*")
            )
            result.segment_count = len(result.output_files)

            if not result.output_files:
                result.error_code = "E7003"
                result.error_message = "E01 セグメントファイルが生成されませんでした"
                logger.error(result.error_message)
                return result

            full_output = result.ewfacquire_stdout
            result.md5 = self._extract_hash_from_output(full_output, "MD5")
            result.sha256 = self._extract_hash_from_output(full_output, "SHA256")
            result.acquired_bytes = self._extract_written_bytes(full_output)
            result.total_bytes = result.acquired_bytes

            result.success = True
            self._current_progress["status"] = "completed"
            self._current_progress["percent"] = 100.0
            if result.acquired_bytes > 0:
                self._current_progress["acquired_bytes"] = result.acquired_bytes
            if result.total_bytes > 0:
                self._current_progress["total_bytes"] = result.total_bytes

            logger.info(
                "E01 取得成功: %s segments, %s bytes, MD5=%s, SHA256=%s",
                result.segment_count,
                f"{result.acquired_bytes:,}",
                result.md5,
                result.sha256,
            )

        except asyncio.CancelledError:
            await self._terminate_process()
            result.error_code = "E3006"
            result.error_message = "ユーザーによりキャンセルされました"
            raise
        except (OSError, IOError) as e:
            result.error_code = "E7002"
            result.error_message = str(e)
            logger.error("E01 取得 I/O エラー: %s", e, exc_info=True)
        except Exception as e:
            result.error_code = "E7002"
            result.error_message = str(e)
            logger.error("E01 取得例外: %s", e, exc_info=True)
        finally:
            self._process = None
            E01Writer._attach_e01_incomplete_files(result, params)

        return result

    async def verify(self, e01_first_path: str) -> E01VerifyResult:
        result = E01VerifyResult()

        ver_path = E01Writer._resolve_ewfverify_path()
        if not ver_path or not Path(ver_path).is_file():
            result.skipped = True
            result.skip_reason = (
                "ewfverify が設定されていないため検証をスキップしました"
            )
            logger.warning(result.skip_reason)
            return result

        try:
            log_path = str(Path(e01_first_path).with_name("image_ewfverify.log"))
            cmd = [
                ver_path,
                "-l",
                log_path,
                "-d",
                "sha256",
                e01_first_path,
            ]
            result.log_file_path = log_path

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **self._subprocess_kwargs(),
            )
            stdout_data, stderr_data = await proc.communicate()
            # ProactorEventLoop の transport クリーンアップ競合を緩和
            try:
                if hasattr(proc, "_transport") and proc._transport is not None:
                    proc._transport.close()
            except Exception:
                pass
            output = stdout_data.decode("utf-8", errors="replace")
            if stderr_data:
                output += "\n" + stderr_data.decode("utf-8", errors="replace")

            result.return_code = proc.returncode if proc.returncode is not None else -1
            result.output = output

            for match in re.finditer(EWFVERIFY_STORED_HASH_PATTERN, output):
                key = E01Writer._normalize_ewf_algo_key(match.group(1))
                result.stored_hashes[key] = match.group(2).lower()
            for match in re.finditer(EWFVERIFY_COMPUTED_HASH_PATTERN, output):
                key = E01Writer._normalize_ewf_algo_key(match.group(1))
                result.computed_hashes[key] = match.group(2).lower()

            result.verified = result.return_code == 0 and bool(
                re.search(EWFVERIFY_SUCCESS_PATTERN, output)
            )

            if result.verified:
                logger.info("E01 検証成功 (ewfverify: SUCCESS)")
            else:
                logger.error("E01 検証失敗: return_code=%s", result.return_code)

        except Exception as e:
            result.error_message = str(e)
            logger.error("ewfverify 実行エラー: %s", e, exc_info=True)

        return result

    async def info(self, e01_path: str) -> E01InfoResult:
        """指定 E01 ファイルに対して ewfinfo を実行し stdout をパースする。"""
        result = E01InfoResult()
        ewfinfo_path = E01Writer._resolve_ewfinfo_path()
        if not ewfinfo_path or not Path(ewfinfo_path).is_file():
            result.error_message = "ewfinfo.exe not found"
            return result

        if len(e01_path) > 240:
            result.error_message = "path too long for ewfinfo (Windows)"
            logger.warning("ewfinfo をスキップ: %s", result.error_message)
            return result

        cmd = [ewfinfo_path, e01_path]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **self._subprocess_kwargs(),
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            try:
                if hasattr(proc, "_transport") and proc._transport is not None:
                    proc._transport.close()
            except Exception:
                pass
            result.return_code = proc.returncode if proc.returncode is not None else -1
            result.raw_output = stdout_bytes.decode("utf-8", errors="replace")
            if stderr_bytes:
                result.raw_output += "\n" + stderr_bytes.decode("utf-8", errors="replace")

            lines = result.raw_output.splitlines()
            if lines and lines[0].strip().lower().startswith("ewfinfo"):
                result.ewfinfo_version = lines[0].replace("ewfinfo", "", 1).strip()

            if proc.returncode == 0:
                result.success = True
                result.sections = E01Writer._parse_ewfinfo_output(result.raw_output)
            else:
                result.error_message = (
                    stderr_bytes.decode("utf-8", errors="replace").strip()
                )
        except Exception as e:
            result.error_message = str(e)
            logger.warning("ewfinfo 実行エラー: %s", e)

        return result

    @staticmethod
    def _parse_ewfinfo_output(raw: str) -> dict[str, dict[str, str]]:
        """ewfinfo stdout を {セクション名: {キー: 値}} にパースする。"""
        sections: dict[str, dict[str, str]] = {}
        current_section = "General"
        for line in raw.splitlines():
            line_stripped = line.strip()
            section_match = EWFINFO_SECTION_PATTERN.match(line_stripped)
            if section_match:
                current_section = section_match.group(1).strip()
                sections.setdefault(current_section, {})
                continue
            kv_match = EWFINFO_KV_PATTERN.match(line)
            if kv_match:
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip()
                sections.setdefault(current_section, {})
                sections[current_section][key] = value
        return sections

    async def cancel(self) -> None:
        self._cancel_requested = True
        await self._terminate_process()

    async def _terminate_process(self) -> None:
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                logger.info("ewfacquire プロセスを停止しました")
            except ProcessLookupError:
                pass

    async def _read_stream_cr_aware(
        self,
        stream: Optional[asyncio.StreamReader],
        line_buffer: list[str],
        parse_progress: bool = False,
    ) -> None:
        """
        ewfacquire は進捗を \\r で同一行上書きする。readline() は \\n まで待つため
        進捗がバッファに溜まり UI が更新されない。\\r / \\n のいずれでも行を確定する。
        """
        if stream is None:
            return

        line_buf = bytearray()

        def flush_line() -> None:
            if not line_buf:
                return
            line = line_buf.decode("utf-8", errors="replace").strip()
            line_buf.clear()
            if not line:
                return
            line_buffer.append(line)
            if parse_progress:
                self._parse_progress_line(line)

        try:
            while True:
                chunk = await stream.read(4096)
                if not chunk:
                    flush_line()
                    break
                for ch in chunk:
                    if ch in (0x0D, 0x0A):
                        flush_line()
                    else:
                        line_buf.append(ch)
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug("ewfacquire ストリーム読取終了: %s", e)
            flush_line()

    def _emit_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(dict(self._current_progress))

    def _parse_progress_line(self, line: str) -> None:
        """ewfacquire の stdout 行を解析（Status / acquired / completion の 3 行ブロック対応）。"""

        m = E01_PROGRESS_PATTERN.search(line)
        if m:
            self._current_progress["percent"] = float(m.group(1))
            self._current_progress["status"] = "imaging"
            self._current_progress["raw_line"] = line
            self._emit_progress()
            return

        m = E01_ACQUIRED_PATTERN.search(line)
        if m:
            self._current_progress["acquired_bytes"] = int(m.group(1))
            self._current_progress["total_bytes"] = int(m.group(2))
            self._current_progress["raw_line"] = line
            self._emit_progress()
            return

        m = E01_SPEED_PATTERN.search(line)
        if m:
            self._current_progress["remaining"] = m.group(1).strip()
            self._current_progress["speed_display"] = f"{m.group(2)} MiB/s"
            self._current_progress["speed_bytes"] = int(m.group(3))
            self._current_progress["raw_line"] = line
            self._emit_progress()
            return

        m = E01_HASH_PATTERN.search(line)
        if m:
            algo = E01Writer._normalize_ewf_algo_key(m.group(1))
            self._current_progress[f"hash_{algo.lower()}"] = m.group(2).lower()
            self._current_progress["raw_line"] = line
            self._emit_progress()
            return

        m = E01_WRITTEN_PATTERN.search(line)
        if m:
            self._current_progress["written_bytes"] = int(m.group(1))
            self._current_progress["raw_line"] = line
            self._emit_progress()

    @staticmethod
    def _normalize_ewf_algo_key(name: str) -> str:
        """SHA-1 / SHA-256 等を MD5 / SHA1 / SHA256 キーに正規化"""
        return re.sub(r"[^A-Za-z0-9]", "", name).upper()

    @staticmethod
    def _extract_hash_from_output(output: str, algo: str) -> str:
        want = E01Writer._normalize_ewf_algo_key(algo)
        for match in E01_HASH_PATTERN.finditer(output):
            if E01Writer._normalize_ewf_algo_key(match.group(1)) == want:
                return match.group(2).lower()
        return ""

    @staticmethod
    def _extract_written_bytes(output: str) -> int:
        match = E01_WRITTEN_PATTERN.search(output)
        if match:
            return int(match.group(1))
        match2 = re.search(
            r"Written:\s+.*?\((\d+)\s+bytes\)", output, re.IGNORECASE | re.DOTALL
        )
        if match2:
            return int(match2.group(1))
        return 0

    @staticmethod
    def _subprocess_kwargs() -> dict:
        import sys

        if sys.platform == "win32":
            return {"creationflags": 0x08000000}
        return {}
