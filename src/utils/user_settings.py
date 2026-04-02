"""
設定画面の値を data/user_settings.json に永続化し、環境変数経由で get_config() に反映する。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from src.utils.constants import BUFFER_SIZE_OPTIONS

logger = logging.getLogger("mfeps.user_settings")

_FILENAME = "user_settings.json"


def user_settings_path(data_dir: Path) -> Path:
    return data_dir / _FILENAME


def apply_user_settings_to_environ(data_dir: Path) -> None:
    """起動時: JSON の environment セクションを os.environ に反映（get_config より前）。"""
    path = user_settings_path(data_dir)
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as e:
        logger.warning("user_settings.json の読込に失敗: %s", e)
        return

    env_block = data.get("environment") if isinstance(data, dict) else None
    if not isinstance(env_block, dict):
        # 旧形式: フラットな MFEPS_* のみ
        if isinstance(data, dict) and any(
            k.startswith("MFEPS_") or k.startswith("EWF") for k in data
        ):
            env_block = data
        else:
            return

    for key, val in env_block.items():
        if not isinstance(key, str):
            continue
        if val is None:
            continue
        os.environ[key] = str(val) if not isinstance(val, bool) else (
            "true" if val else "false"
        )


def _stored_to_payload(
    stored: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """保存用 JSON（environment + ui）。"""
    buf_label = stored.get(
        "buffer_label", defaults.get("buffer_label", "1 MiB")
    )
    buf_bytes = BUFFER_SIZE_OPTIONS.get(buf_label, 1_048_576)

    env_flat: dict[str, Any] = {
        "MFEPS_SYSLOG_HOST": str(
            stored.get("syslog_host", defaults.get("syslog_host", ""))
        ),
        "MFEPS_SYSLOG_PORT": int(
            stored.get("syslog_port", defaults.get("syslog_port", 514))
        ),
        "MFEPS_SYSLOG_PROTO": str(
            stored.get("syslog_proto", defaults.get("syslog_proto", "udp"))
        ),
        "MFEPS_AUDIT_JSONL_ENABLED": bool(
            stored.get(
                "audit_jsonl_enabled",
                defaults.get("audit_jsonl_enabled", False),
            )
        ),
        "MFEPS_AUDIT_JSONL_PATH": str(
            stored.get(
                "audit_jsonl_path",
                defaults.get("audit_jsonl_path", "logs/audit_export.jsonl"),
            )
        ),
        "MFEPS_OUTPUT_DIR": stored.get(
            "output_dir", defaults.get("output_dir", "./output")
        ),
        "MFEPS_BUFFER_SIZE": int(buf_bytes),
        "MFEPS_FONT_SIZE": int(
            stored.get("font_size", defaults.get("font_size", 16))
        ),
        "MFEPS_THEME": stored.get("theme", defaults.get("theme", "dark")),
        "MFEPS_RFC3161_ENABLED": bool(
            stored.get(
                "rfc3161_enabled", defaults.get("rfc3161_enabled", False)
            )
        ),
        "MFEPS_RFC3161_TSA_URL": stored.get(
            "tsa_url", defaults.get("tsa_url", "http://timestamp.digicert.com")
        ),
        "MFEPS_DOUBLE_READ_OPTICAL": bool(
            stored.get("double_read", defaults.get("double_read", False))
        ),
        "EWFACQUIRE_PATH": (
            stored.get("ewfacquire_path")
            or defaults.get("ewfacquire_path")
            or ""
        ),
        "EWFVERIFY_PATH": (
            stored.get("ewfverify_path")
            or defaults.get("ewfverify_path")
            or ""
        ),
    }

    ui_keys = (
        "hash_md5",
        "hash_sha1",
        "hash_sha256",
        "hash_sha512",
        "error_action",
        "e01_compression",
        "e01_segment_size",
        "e01_ewf_format",
        "buffer_label",
        "ffmpeg_path",
        "target_size",
        "locale",
        "syslog_host",
        "syslog_port",
        "syslog_proto",
        "audit_jsonl_enabled",
        "audit_jsonl_path",
    )
    ui_block = {k: stored[k] for k in ui_keys if k in stored}

    return {"environment": env_flat, "ui": ui_block}


def persist_user_settings_from_storage(
    stored: dict[str, Any],
    *,
    data_dir: Path,
    config_defaults: dict[str, Any],
) -> None:
    """保存ボタン: JSON 書き込み + os.environ 更新。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = _stored_to_payload(stored, config_defaults)
    path = user_settings_path(data_dir)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    env_flat = payload["environment"]
    for k, v in env_flat.items():
        os.environ[k] = (
            str(v) if not isinstance(v, bool) else ("true" if v else "false")
        )
    logger.info("ユーザー設定を保存しました: %s", path)


def merge_file_into_storage(stored: dict[str, Any], data_dir: Path) -> None:
    """起動時: JSON を storage にマージ（保存済み UI ・パスを復元）。"""
    path = user_settings_path(data_dir)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    env_block = data.get("environment") if isinstance(data, dict) else None
    ui_block = data.get("ui") if isinstance(data, dict) else None

    if isinstance(env_block, dict):
        _merge_env_into_storage(stored, env_block)
    elif isinstance(data, dict) and not env_block:
        # 旧フラット形式
        flat = {
            k: v
            for k, v in data.items()
            if isinstance(k, str)
            and (k.startswith("MFEPS_") or k.startswith("EWF"))
        }
        if flat:
            _merge_env_into_storage(stored, flat)

    if isinstance(ui_block, dict):
        for k, v in ui_block.items():
            stored[k] = v


def _merge_env_into_storage(stored: dict[str, Any], env_block: dict) -> None:
    m = {
        "MFEPS_OUTPUT_DIR": "output_dir",
        "MFEPS_FONT_SIZE": "font_size",
        "MFEPS_THEME": "theme",
        "MFEPS_RFC3161_ENABLED": "rfc3161_enabled",
        "MFEPS_RFC3161_TSA_URL": "tsa_url",
        "MFEPS_DOUBLE_READ_OPTICAL": "double_read",
        "EWFACQUIRE_PATH": "ewfacquire_path",
        "EWFVERIFY_PATH": "ewfverify_path",
    }
    for ek, sk in m.items():
        if ek in env_block and env_block[ek] is not None:
            val = env_block[ek]
            if sk == "font_size":
                try:
                    stored[sk] = int(val)
                except (ValueError, TypeError):
                    stored[sk] = val
            elif sk in ("rfc3161_enabled", "double_read"):
                stored[sk] = _parse_bool(val)
            else:
                stored[sk] = val

    bs = env_block.get("MFEPS_BUFFER_SIZE")
    if bs is not None:
        try:
            bint = int(bs)
            for label, val in BUFFER_SIZE_OPTIONS.items():
                if val == bint:
                    stored["buffer_label"] = label
                    break
        except (ValueError, TypeError):
            pass


def _parse_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None
