from datetime import datetime, timedelta, timezone

import pytest

from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
    init_db,
)
from paralert.application.check_conditions import CheckConditionsUseCase
from paralert.domain.models import CheckResult, Settings, Summit, WindData
from paralert.domain.ports import NotificationPort, SettingsRepository, WeatherPort

_now = datetime.now(timezone.utc)
DATE_TODAY = _now.strftime("%Y-%m-%d")
DATE_TOMORROW = (_now + timedelta(days=1)).strftime("%Y-%m-%d")


class FakeWeather(WeatherPort):
    def __init__(self, speed: float):
        self._speed = speed

    async def fetch_wind(self, lat, lon, altitudes_m) -> WindData:
        return WindData(
            hourly={
                alt: {
                    f"{date}T{h:02d}:00": self._speed
                    for date in (DATE_TODAY, DATE_TOMORROW)
                    for h in range(24)
                }
                for alt in altitudes_m
            }
        )


class FakeNotifier(NotificationPort):
    def __init__(self):
        self.calls: list[tuple[Summit, CheckResult]] = []

    async def send(self, summit: Summit, result: CheckResult) -> None:
        self.calls.append((summit, result))


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def populated_db(db):
    summit_repo = SqliteSummitRepository(db)
    summit_repo.add(Summit(id=None, name="Test Peak", lat=45.0, lon=5.0, altitudes_m=(2000, 3000), enabled=True))
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
    uc = _make_use_case(populated_db, FakeWeather(speed=10.0), notifier)

    results = await uc.execute()

    assert len(results) == 2  # J and J+1
    assert all(len(r.calm_hours) > 0 for r in results)
    assert len(notifier.calls) == 2


@pytest.mark.anyio
async def test_windy_conditions_no_notification(populated_db):
    notifier = FakeNotifier()
    uc = _make_use_case(populated_db, FakeWeather(speed=50.0), notifier)

    results = await uc.execute()

    assert all(r.calm_hours == () for r in results)
    assert notifier.calls == []


@pytest.mark.anyio
async def test_results_persisted(populated_db):
    uc = _make_use_case(populated_db, FakeWeather(speed=10.0), FakeNotifier())
    await uc.execute()

    # 2 results per summit (J and J+1), both at same checked_at
    last = SqliteCheckResultRepository(populated_db).last_by_summit()
    assert len(last) == 2
