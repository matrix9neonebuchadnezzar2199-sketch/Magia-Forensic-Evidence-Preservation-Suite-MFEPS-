"""
MFEPS v2.2.0 — 軽量 i18n サービス
JSON ロケールファイルから翻訳テキストを返す。
"""
import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mfeps.i18n")

_DEFAULT_LOCALE = "ja"
_SUPPORTED_LOCALES = ("ja", "en")


class I18nService:
    """
    シンプルな JSON ベースの翻訳サービス。

    ロケールファイルは src/locales/{locale}.json に配置する。
    キーはドット区切り階層 (e.g. "dashboard.title") を使用。
    """

    def __init__(self, locales_dir: Optional[Path] = None):
        self._locales_dir = locales_dir or (
            Path(__file__).resolve().parent.parent / "locales"
        )
        self._current_locale: str = _DEFAULT_LOCALE
        self._translations: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        """サポート対象の全ロケールファイルをプリロード"""
        for loc in _SUPPORTED_LOCALES:
            fpath = self._locales_dir / f"{loc}.json"
            if fpath.is_file():
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        self._translations[loc] = json.load(f)
                    logger.debug(
                        "ロケール読み込み: %s (%d keys)",
                        loc,
                        len(self._translations[loc]),
                    )
                except OSError as e:
                    logger.warning("ロケール読み込み失敗: %s — %s", fpath, e)
            else:
                logger.debug("ロケールファイル未検出: %s", fpath)

    @property
    def locale(self) -> str:
        return self._current_locale

    def set_locale(self, locale: str) -> None:
        if locale not in _SUPPORTED_LOCALES:
            logger.warning(
                "未対応ロケール: %s (対応: %s)", locale, _SUPPORTED_LOCALES
            )
            return
        self._current_locale = locale
        logger.info("ロケール変更: %s", locale)

    def t(self, key: str, **kwargs) -> str:
        """
        翻訳キーに対応するテキストを返す。

        ドット区切りでネスト辞書を参照する。
        キーが見つからない場合はフォールバックロケール → キー文字列を返す。
        kwargs があれば str.format() で埋め込む。
        """
        text = self._resolve(key, self._current_locale)
        if text is None and self._current_locale != _DEFAULT_LOCALE:
            text = self._resolve(key, _DEFAULT_LOCALE)
        if text is None:
            return key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def _resolve(self, key: str, locale: str) -> Optional[str]:
        data = self._translations.get(locale)
        if not data:
            return None
        parts = key.split(".")
        cur: object = data
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        return cur if isinstance(cur, str) else None

    @property
    def supported_locales(self) -> tuple[str, ...]:
        return _SUPPORTED_LOCALES


_i18n_instance: Optional[I18nService] = None
_i18n_lock = threading.Lock()


def get_i18n() -> I18nService:
    global _i18n_instance
    if _i18n_instance is not None:
        return _i18n_instance
    with _i18n_lock:
        if _i18n_instance is None:
            _i18n_instance = I18nService()
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    """ショートカット: get_i18n().t(key, **kwargs)"""
    return get_i18n().t(key, **kwargs)


def reset_i18n_for_tests() -> None:
    """単体テスト用"""
    global _i18n_instance
    with _i18n_lock:
        _i18n_instance = None
