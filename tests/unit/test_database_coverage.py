"""database.py の追加カバレッジ"""
import pytest

from src.models.database import get_engine, init_database, session_scope
from src.models.schema import Case


def test_init_database_creates_db(tmp_path):
    db_path = tmp_path / "test_cov.db"
    init_database(db_path)
    assert db_path.exists()


def test_session_scope_commit(tmp_path):
    init_database(tmp_path / "test_sess.db")
    with session_scope() as session:
        c = Case(case_number="COV-001", case_name="Coverage Test")
        session.add(c)
    with session_scope() as session:
        assert session.query(Case).count() == 1


def test_session_scope_rollback(tmp_path):
    init_database(tmp_path / "test_rb.db")
    with pytest.raises(ValueError, match="force rollback"):
        with session_scope() as session:
            c = Case(case_number="COV-RB", case_name="Rollback")
            session.add(c)
            raise ValueError("force rollback")
    with session_scope() as session:
        assert (
            session.query(Case).filter_by(case_number="COV-RB").count() == 0
        )


def test_get_engine(tmp_path):
    init_database(tmp_path / "test_eng.db")
    engine = get_engine()
    assert engine is not None
