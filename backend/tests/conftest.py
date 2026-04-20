from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    base = tmp_path_factory.mktemp("backend-tests")
    return Path(base) / "test.db"


@pytest.fixture(scope="session")
def app(test_db_path):
    import core.db as core_db
    from services import runtime

    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    core_db.engine = test_engine
    core_db.SessionLocal = test_session_local
    runtime.engine = test_engine
    runtime.SessionLocal = test_session_local
    runtime.COOKIE_SECURE = False
    runtime._RUNTIME_INITIALIZED = False

    from app import create_app

    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_login(client):
    setup_resp = client.post("/api/auth/setup", json={"username": "xiaoyao", "password": "admin123"})
    assert setup_resp.status_code in (200, 400)
    r = client.post("/api/auth/login", json={"username": "xiaoyao", "password": "admin123"})
    assert r.status_code == 200
    return client
