import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        secret_key="test-secret-key",
        auto_migrate=False,
        enable_scheduler=False,
        data_dir=str(tmp_path / "data"),
        upload_dir=str(tmp_path / "data" / "uploads"),
        backup_dir=str(tmp_path / "data" / "backups"),
        frontend_dist=str(tmp_path / "dist"),
    )
    app = create_app(settings)
    Base.metadata.create_all(bind=app.state.engine)
    with TestClient(app) as test_client:
        yield test_client
