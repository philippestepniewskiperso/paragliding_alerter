import threading
import time

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from paralert.adapters.storage.sqlite import init_db
from paralert.config import AppConfig
from paralert.entrypoints.api import app

PORT = 19080
BASE_URL = f"http://127.0.0.1:{PORT}"

pytestmark = pytest.mark.frontend


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    init_db(db_path)

    import paralert.config as config_module

    config_module._instance = AppConfig(db_path=db_path, host="127.0.0.1", port=PORT)

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.0)

    yield BASE_URL

    server.should_exit = True
    thread.join(timeout=3)


def test_page_loads(page: Page, live_server):
    page.goto(live_server)
    expect(page.locator("h1")).to_contain_text("Paralert")
    expect(page.locator("[data-tab='summits']")).to_be_visible()
    expect(page.locator("[data-tab='settings']")).to_be_visible()
    expect(page.locator("[data-tab='status']")).to_be_visible()


def test_add_summit(page: Page, live_server):
    page.goto(live_server)
    page.click("[data-tab='summits']")
    page.click("button:has-text('Ajouter')")

    page.fill("[name='name']", "Chamechaude")
    page.fill("[name='lat']", "45.2833")
    page.fill("[name='lon']", "5.7667")
    page.check("[data-alt='2000']")
    page.check("[data-alt='3000']")

    page.click("button:has-text('Enregistrer')")
    expect(page.locator("#summits-table")).to_contain_text("Chamechaude")


def test_settings_save(page: Page, live_server):
    page.goto(live_server)
    page.click("[data-tab='settings']")

    page.fill("[name='wind_calm_kmh']", "20")
    page.click("[data-action='save-settings']")

    expect(page.locator("[data-saved]")).to_be_visible()


def test_trigger_check_shows_spinner(page: Page, live_server):
    page.goto(live_server)
    page.click("[data-tab='status']")
    page.click("button:has-text('Vérifier')")

    expect(page.locator("[data-checking]")).to_be_visible()
