import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DEV_MODE", "1")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as app_main  # noqa: E402
from database import Base  # noqa: E402


@pytest.fixture()
def app_client(tmp_path):
    db_file = tmp_path / "trading_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app_main.app.dependency_overrides[app_main.get_db] = override_get_db

    with TestClient(app_main.app) as client:
        yield client

    app_main.app.dependency_overrides.clear()
    test_engine.dispose()
