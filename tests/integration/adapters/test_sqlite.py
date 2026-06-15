import pytest

from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
    init_db,
)
from paralert.domain.models import CheckResult, Settings, SlotConfig, Summit


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _summit(**kwargs) -> Summit:
    defaults = dict(id=None, name="Test", lat=45.0, lon=5.0, altitudes_m=(2000, 3000), enabled=True)
    return Summit(**(defaults | kwargs))


def _full_settings(**kwargs) -> Settings:
    defaults = dict(
        ntfy_url="https://ntfy.sh", ntfy_topic="paralert", wind_calm_kmh=15.0,
        cron_expression="0 6 * * *", season_start="04-15", season_end="11-15",
        require_no_snow=True, only_off_peak=False, timezone="Europe/Paris",
        cloud_cover_max_pct=50.0, custom_slots=(),
    )
    return Settings(**(defaults | kwargs))


class TestSummitRepository:
    def test_add_and_list(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        assert s.id is not None
        assert repo.list() == [s]

    def test_list_enabled_only(self, db):
        repo = SqliteSummitRepository(db)
        active = repo.add(_summit(name="Active", enabled=True))
        repo.add(_summit(name="Inactive", enabled=False))
        assert repo.list(enabled_only=True) == [active]

    def test_get(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        assert repo.get(s.id) == s

    def test_get_missing_raises(self, db):
        repo = SqliteSummitRepository(db)
        with pytest.raises(KeyError):
            repo.get(999)

    def test_update(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        updated = Summit(id=s.id, name="Updated", lat=46.0, lon=6.0, altitudes_m=(4000,), enabled=False)
        result = repo.update(updated)
        assert result.name == "Updated"
        assert result.altitudes_m == (4000,)

    def test_delete(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        repo.delete(s.id)
        assert repo.list() == []

    def test_add_with_custom_slots(self, db):
        repo = SqliteSummitRepository(db)
        slots = (SlotConfig(start_hour=6, end_hour=9), SlotConfig(start_hour=17, end_hour=20))
        s = repo.add(_summit(custom_slots=slots))
        assert s.custom_slots == slots
        assert repo.get(s.id).custom_slots == slots

    def test_add_without_custom_slots_is_none(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        assert s.custom_slots is None

    def test_update_sets_custom_slots(self, db):
        repo = SqliteSummitRepository(db)
        s = repo.add(_summit())
        slots = (SlotConfig(start_hour=5, end_hour=8),)
        updated = Summit(id=s.id, name=s.name, lat=s.lat, lon=s.lon, altitudes_m=s.altitudes_m, enabled=s.enabled, custom_slots=slots)
        result = repo.update(updated)
        assert result.custom_slots == slots

    def test_update_clears_custom_slots_to_none(self, db):
        repo = SqliteSummitRepository(db)
        slots = (SlotConfig(start_hour=6, end_hour=9),)
        s = repo.add(_summit(custom_slots=slots))
        cleared = Summit(id=s.id, name=s.name, lat=s.lat, lon=s.lon, altitudes_m=s.altitudes_m, enabled=s.enabled, custom_slots=None)
        result = repo.update(cleared)
        assert result.custom_slots is None


class TestSettingsRepository:
    def test_defaults(self, db):
        repo = SqliteSettingsRepository(db)
        s = repo.get()
        assert s.ntfy_url == "https://ntfy.sh"
        assert s.wind_calm_kmh == 15.0
        assert s.season_start == "04-15"
        assert s.require_no_snow is True
        assert s.cloud_cover_max_pct == 50.0

    def test_save_and_get(self, db):
        repo = SqliteSettingsRepository(db)
        new = _full_settings(ntfy_url="https://custom.ntfy", ntfy_topic="my-topic", wind_calm_kmh=20.0, cron_expression="0 7 * * *")
        repo.save(new)
        assert repo.get() == new

    def test_defaults_custom_slots_empty(self, db):
        repo = SqliteSettingsRepository(db)
        s = repo.get()
        assert s.custom_slots == ()

    def test_save_and_get_custom_slots(self, db):
        repo = SqliteSettingsRepository(db)
        slots = (SlotConfig(start_hour=6, end_hour=9), SlotConfig(start_hour=17, end_hour=20))
        new = _full_settings(custom_slots=slots)
        repo.save(new)
        assert repo.get().custom_slots == slots


class TestCheckResultRepository:
    def test_save_and_last_by_summit(self, db):
        summit_repo = SqliteSummitRepository(db)
        s = summit_repo.add(_summit())

        repo = SqliteCheckResultRepository(db)
        r = CheckResult(summit_id=s.id, target_date="2026-05-20", calm_slots=(), max_wind_kmh=12.0, checked_at="2026-05-20T06:00:00+00:00")
        repo.save(r)

        last = repo.last_by_summit()
        assert len(last) == 1
        assert last[0].calm_slots == ()
