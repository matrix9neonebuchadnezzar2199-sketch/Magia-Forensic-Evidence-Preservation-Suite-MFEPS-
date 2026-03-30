"""法的同意 — DB 初期化が必要なためスキップ可能なスモークテスト"""


def test_legal_constants_import():
    from src.ui.components import legal_consent_dialog

    assert legal_consent_dialog.LEGAL_CONSENT_VERSION
