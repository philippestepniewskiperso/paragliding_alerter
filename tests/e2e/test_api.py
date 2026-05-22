import pytest
from fastapi.testclient import TestClient

from paralert.adapters.storage.sqlite import init_db
from paralert.config import AppConfig, get_app_config
from paralert.entrypoints.api import app


@pytest.fixture(autouse=True)
def override_config(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    cfg = AppConfig(db_path=db_path)
    monkeypatch.setattr("paralert.config._instance", cfg)
    init_db(db_path)


@pytest.fixture
def client():
    return TestClient(app)


class TestSummitsAPI:
    def test_list_empty(self, client):
        r = client.get("/api/summits/")
        assert r.status_code == 200
        assert r.json() == []

    def test_create(self, client):
        payload = {
            "name": "Chamechaude",
            "lat": 45.28,
            "lon": 5.77,
            "altitudes_m": [2000, 3000],
            "enabled": True,
        }
        r = client.post("/api/summits/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["id"] is not None
        assert data["name"] == "Chamechaude"

    def test_update(self, client):
        r = client.post(
            "/api/summits/",
            json={
                "name": "Old",
                "lat": 45.0,
                "lon": 5.0,
                "altitudes_m": [2000],
                "enabled": True,
            },
        )
        id = r.json()["id"]
        r = client.put(
            f"/api/summits/{id}",
            json={
                "name": "New",
                "lat": 46.0,
                "lon": 6.0,
                "altitudes_m": [3000],
                "enabled": False,
            },
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New"

    def test_delete(self, client):
        r = client.post(
            "/api/summits/",
            json={
                "name": "Del",
                "lat": 45.0,
                "lon": 5.0,
                "altitudes_m": [2000],
                "enabled": True,
            },
        )
        id = r.json()["id"]
        r = client.delete(f"/api/summits/{id}")
        assert r.status_code == 204
        assert client.get("/api/summits/").json() == []

    def test_delete_missing_returns_404(self, client):
        r = client.delete("/api/summits/9999")
        assert r.status_code == 404

    def test_toggle(self, client):
        r = client.post(
            "/api/summits/",
            json={
                "name": "T",
                "lat": 45.0,
                "lon": 5.0,
                "altitudes_m": [2000],
                "enabled": True,
            },
        )
        id = r.json()["id"]
        r = client.patch(f"/api/summits/{id}/toggle")
        assert r.status_code == 200
        assert r.json()["enabled"] is False


class TestSettingsAPI:
    def test_get_defaults(self, client):
        r = client.get("/api/settings/")
        assert r.status_code == 200
        data = r.json()
        assert data["ntfy_url"] == "https://ntfy.sh"
        assert data["wind_calm_kmh"] == 15.0

    def test_update(self, client):
        payload = {
            "ntfy_url": "https://ntfy.example.com",
            "ntfy_topic": "test",
            "wind_calm_kmh": 20.0,
            "cron_expression": "0 7 * * *",
            "season_start": "04-15",
            "season_end": "11-15",
            "require_no_snow": True,
            "only_off_peak": False,
            "timezone": "Europe/Paris",
            "cloud_cover_max_pct": 50.0,
        }
        r = client.put("/api/settings/", json=payload)
        assert r.status_code == 200
        assert r.json()["wind_calm_kmh"] == 20.0


class TestChecksAPI:
    def test_last_empty(self, client):
        r = client.get("/api/checks/last")
        assert r.status_code == 200
        assert r.json() == []
