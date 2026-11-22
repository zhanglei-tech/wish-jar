import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"


def make_client(tmp_path, include_manifest: bool = True) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><body>心愿罐</body></html>",
        encoding="utf-8",
    )
    (dist / "sw.js").write_text(
        "self.addEventListener('fetch', () => {})\n",
        encoding="utf-8",
    )
    if include_manifest:
        (dist / "manifest.webmanifest").write_text(
            json.dumps({"name": "心愿罐", "display": "standalone"}),
            encoding="utf-8",
        )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        secret_key="test-secret-key",
        auto_migrate=False,
        enable_scheduler=False,
        data_dir=str(tmp_path / "data"),
        upload_dir=str(tmp_path / "data" / "uploads"),
        backup_dir=str(tmp_path / "data" / "backups"),
        frontend_dist=str(dist),
    )
    return TestClient(create_app(settings))


@pytest.fixture()
def pwa_client(tmp_path):
    with make_client(tmp_path) as client:
        yield client


def test_manifest_is_served_with_no_cache(pwa_client):
    response = pwa_client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    assert response.headers["cache-control"] == "no-cache"
    assert response.json()["display"] == "standalone"


def test_service_worker_is_served_without_caching(pwa_client):
    response = pwa_client.get("/sw.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["service-worker-allowed"] == "/"
    assert "caches." not in response.text
    assert "respondWith(" not in response.text


def test_index_and_spa_fallback_are_not_cached(pwa_client):
    for path in ("/", "/child/wish-jar"):
        response = pwa_client.get(path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["cache-control"] == "no-cache"


def test_missing_pwa_file_does_not_fall_back_to_index(tmp_path):
    with make_client(tmp_path, include_manifest=False) as client:
        assert client.get("/manifest.webmanifest").status_code == 404


def test_version_endpoint_is_no_store_and_tracks_index(tmp_path):
    with make_client(tmp_path) as client:
        first = client.get("/api/version")

        assert first.status_code == 200
        assert first.headers["cache-control"] == "no-store"
        assert len(first.json()["build_id"]) == 12

        (tmp_path / "dist" / "index.html").write_text(
            "<!doctype html><html><body>新版本</body></html>",
            encoding="utf-8",
        )
        second = client.get("/api/version")

        assert second.status_code == 200
        assert second.json()["build_id"] != first.json()["build_id"]


def test_source_manifest_and_icons_exist():
    manifest = json.loads(
        (PUBLIC / "manifest.webmanifest").read_text(encoding="utf-8")
    )

    assert manifest["display"] == "standalone"
    assert {icon["sizes"] for icon in manifest["icons"]} >= {"192x192", "512x512"}
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])

    for icon in manifest["icons"]:
        icon_path = PUBLIC / icon["src"].lstrip("/")
        assert icon_path.is_file(), icon_path
        assert icon_path.stat().st_size > 0


def test_index_links_manifest_and_source_worker_has_no_cache_logic():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    worker = (PUBLIC / "sw.js").read_text(encoding="utf-8")

    assert 'rel="manifest"' in index
    assert "/manifest.webmanifest" in index
    assert 'rel="icon"' in index
    assert "/favicon.ico" in index
    assert "/icons/favicon-32.png" in index
    assert "caches." not in worker
    assert "respondWith(" not in worker


def test_favicon_files_exist():
    for name in ("favicon.ico", "icons/favicon-32.png", "icons/favicon-16.png"):
        path = PUBLIC / name
        assert path.is_file(), path
        assert path.stat().st_size > 0
