"""i18n サービスのユニットテスト"""
import json

import pytest

from src.utils.i18n import I18nService, reset_i18n_for_tests


@pytest.fixture
def locale_dir(tmp_path):
    ja = {"app": {"title": "テスト {version}"}, "flat": "フラット値"}
    en = {"app": {"title": "Test {version}"}, "flat": "Flat Value"}
    (tmp_path / "ja.json").write_text(
        json.dumps(ja), encoding="utf-8"
    )
    (tmp_path / "en.json").write_text(
        json.dumps(en), encoding="utf-8"
    )
    return tmp_path


def test_default_locale_is_ja(locale_dir):
    svc = I18nService(locales_dir=locale_dir)
    assert svc.locale == "ja"


def test_translate_nested_key(locale_dir):
    svc = I18nService(locales_dir=locale_dir)
    assert svc.t("app.title", version="2.2") == "テスト 2.2"


def test_translate_flat_key(locale_dir):
    svc = I18nService(locales_dir=locale_dir)
    assert svc.t("flat") == "フラット値"


def test_switch_locale(locale_dir):
    svc = I18nService(locales_dir=locale_dir)
    svc.set_locale("en")
    assert svc.t("flat") == "Flat Value"


def test_missing_key_returns_key(locale_dir):
    svc = I18nService(locales_dir=locale_dir)
    assert svc.t("nonexistent.key") == "nonexistent.key"


def test_fallback_to_default(locale_dir):
    ja = {"only_ja": "日本語のみ"}
    (locale_dir / "ja.json").write_text(
        json.dumps(ja), encoding="utf-8"
    )
    (locale_dir / "en.json").write_text(json.dumps({}), encoding="utf-8")
    svc = I18nService(locales_dir=locale_dir)
    svc.set_locale("en")
    assert svc.t("only_ja") == "日本語のみ"


@pytest.fixture(autouse=True)
def _reset_i18n_singleton():
    reset_i18n_for_tests()
    yield
    reset_i18n_for_tests()
