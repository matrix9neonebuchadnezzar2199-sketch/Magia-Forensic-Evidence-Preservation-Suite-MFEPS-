"""auth_service.py のカバレッジ補完"""

import pytest

from src.models.database import init_database, session_scope
from src.models.schema import User
from src.services.auth_service import AuthService, ensure_default_admin


@pytest.fixture
def db(tmp_path):
    init_database(tmp_path / "auth_cov.db")
    return tmp_path


def test_hash_and_verify():
    auth = AuthService()
    h = auth.hash_password("testpass123")
    assert auth.verify_password("testpass123", h)
    assert not auth.verify_password("wrong", h)


def test_verify_invalid_hash():
    auth = AuthService()
    assert not auth.verify_password("test", "not-a-hash")


def test_authenticate_success(db):
    auth = AuthService()
    with session_scope() as session:
        u = User(
            username="testuser",
            password_hash=auth.hash_password("Pass1234"),
            display_name="Test User",
            role="examiner",
            is_active=True,
        )
        session.add(u)
    result = auth.authenticate("testuser", "Pass1234")
    assert result is not None
    assert result["role"] == "examiner"


def test_authenticate_wrong_password(db):
    auth = AuthService()
    with session_scope() as session:
        u = User(
            username="wrongpw",
            password_hash=auth.hash_password("Correct1"),
            role="viewer",
            is_active=True,
        )
        session.add(u)
    assert auth.authenticate("wrongpw", "Wrong1234") is None


def test_authenticate_inactive(db):
    auth = AuthService()
    with session_scope() as session:
        u = User(
            username="inactive",
            password_hash=auth.hash_password("Pass12345"),
            role="examiner",
            is_active=False,
        )
        session.add(u)
    assert auth.authenticate("inactive", "Pass12345") is None


def test_ensure_default_admin(db):
    ensure_default_admin()
    with session_scope() as session:
        admin = session.query(User).filter_by(username="admin").first()
        assert admin is not None
        assert admin.role == "admin"
