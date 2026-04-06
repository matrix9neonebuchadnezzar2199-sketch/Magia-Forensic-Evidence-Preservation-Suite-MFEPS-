"""MFEPS_E2E_ADMIN_PASSWORD が初回 admin に使われること"""
from __future__ import annotations

from src.models.database import init_database
from src.services.auth_service import AuthService, ensure_default_admin


def test_e2e_env_password_used_for_default_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("MFEPS_E2E_ADMIN_PASSWORD", "E2EValidPass9!")
    init_database(tmp_path / "e2e_admin.db")

    ensure_default_admin()

    auth = AuthService()
    assert auth.authenticate("admin", "E2EValidPass9!") is not None
