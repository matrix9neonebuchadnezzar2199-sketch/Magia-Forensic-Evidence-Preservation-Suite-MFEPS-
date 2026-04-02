"""user_settings 追加分岐"""
import json

from src.utils.user_settings import (
    _merge_env_into_storage,
    _parse_bool,
    merge_file_into_storage,
    user_settings_path,
)


def test_parse_bool_variants():
    assert _parse_bool(None) is None
    assert _parse_bool(True) is True
    assert _parse_bool("1") is True
    assert _parse_bool("no") is False
    assert _parse_bool("maybe") is None


def test_merge_env_sets_buffer_label(tmp_path):
    stored: dict = {}
    _merge_env_into_storage(
        stored,
        {"MFEPS_BUFFER_SIZE": str(1_048_576)},
    )
    assert stored.get("buffer_label") == "1 MiB"


def test_merge_env_font_size_invalid():
    stored: dict = {}
    _merge_env_into_storage(stored, {"MFEPS_FONT_SIZE": "bad"})
    assert stored.get("font_size") == "bad"


def test_merge_file_legacy_flat(tmp_path):
    p = user_settings_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"MFEPS_OUTPUT_DIR": "./legacy", "MFEPS_FONT_SIZE": "20"}),
        encoding="utf-8",
    )
    stored: dict = {}
    merge_file_into_storage(stored, tmp_path)
    assert stored.get("output_dir") == "./legacy"


def test_merge_file_invalid_json(tmp_path):
    p = user_settings_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    merge_file_into_storage({}, tmp_path)


def test_merge_file_missing(tmp_path):
    merge_file_into_storage({}, tmp_path)
