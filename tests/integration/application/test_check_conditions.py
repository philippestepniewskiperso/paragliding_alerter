from datetime import datetime, timedelta, timezone

import pytest

from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
    init_db,
)
from paralert.application.check_conditions import CheckConditionsUseCase
from paralert.domain.models import CheckResult, SurfaceHour, Summit, WindData, WindHour
from paralert.domain.ports import NotificationPort, WeatherPort

_now = datetime.now(timezone.utc)
DATE_TODAY = _now.strftime("%Y-%m-%d")
DATE_TOMORROW = (_now + timedelta(days=1)).strftime("%Y-%m-%d")
DATES = [(_now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

_CALM_SURFACE = SurfaceHour(cloud_cover_pct=0.0, precipitation_mm=0.0, snow_depth_m=0.0)


class FakeWeather(WeatherPort):
    def __init__(self, speed: float):
        self._speed = speed

    async def fetch_wind(self, lat, lon, altitudes_m) -> WindData:
        return WindData(
            hourly={
                alt: {
                    f"{date}T{h:02d}:00": WindHour(speed_kmh=self._speed, direction_deg=45.0)
                    for date in DATES
                    for h in range(24)
                }
                for alt in altitudes_m
            },
            surface={
                f"{date}T{h:02d}:00": _CALM_SURFACE
                for date in DATES
                for h in range(24)
            },
        )


class FakeNotifier(NotificationPort):
    def __init__(self):
        self.calls: list[tuple] = []

    async def send(self, summit, result: CheckResult) -> None:
        self.calls.append((summit, result))


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def populated_db(db):
    SqliteSummitRepository(db).add(Summit(id=None, name="Test Peak", lat=45.0, lon=5.0, altitudes_m=(2000, 3000), enabled=True))
    return db


def _make_use_case(db, weather, notifier) -> CheckConditionsUseCase:
    settings_repo = SqliteSettingsRepository(db)
    return CheckConditionsUseCase(
        weather=weather,
        summits=SqliteSummitRepository(db),
        settings=settings_repo,
        results=SqliteCheckResultRepository(db),
        notifier=notifier,
    )


@pytest.mark.anyio
async def test_calm_conditions_trigger_notification(populated_db):
    notifier = FakeNotifier()
    results = await _make_use_case(populated_db, FakeWeather(speed=10.0), notifier).execute()

    # Results for dates within season (default 04-15 to 11-15) — today is 2026-05-21, all 7 days in season
    assert len(results) > 0
    assert all(len(r.calm_slots) > 0 for r in results)
    assert len(notifier.calls) == len(results)


@pytest.mark.anyio
async def test_windy_conditions_no_notification(populated_db):
    notifier = FakeNotifier()
    results = await _make_use_case(populated_db, FakeWeather(speed=50.0), notifier).execute()

    assert all(r.calm_slots == () for r in results)
    assert notifier.calls == []


@pytest.mark.anyio
async def test_results_persisted(populated_db):
    await _make_use_case(populated_db, FakeWeather(speed=10.0), FakeNotifier()).execute()

    last = SqliteCheckResultRepository(populated_db).last_by_summit()
    # last_by_summit returns one entry per summit (latest checked_at), but multiple target_dates
    assert len(last) >= 1
