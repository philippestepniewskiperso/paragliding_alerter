import pytest

from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
    init_db,
)
from paralert.domain.models import CheckResult, Settings, Summit


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _summit(**kwargs) -> Summit:
    defaults = dict(id=None, name="Test", lat=45.0, lon=5.0, altitudes_m=(2000, 3000), enabled=True)
    return Summit(**(defaults | kwargs))


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


class TestSettingsRepository:
    def test_defaults(self, db):
        repo = SqliteSettingsRepository(db)
        s = repo.get()
        assert s.ntfy_url == "https://ntfy.sh"
        assert s.wind_calm_kmh == 15.0

    def test_save_and_get(self, db):
        repo = SqliteSettingsRepository(db)
        new = Settings(ntfy_url="https://custom.ntfy", ntfy_topic="my-topic", wind_calm_kmh=20.0, cron_expression="0 7 * * *")
        repo.save(new)
        assert repo.get() == new


class TestCheckResultRepository:
    def test_save_and_last_by_summit(self, db):
        summit_repo = SqliteSummitRepository(db)
        s = summit_repo.add(_summit())

        repo = SqliteCheckResultRepository(db)
        r = CheckResult(summit_id=s.id, target_date="2026-05-20", calm_hours=(8, 9), max_wind_kmh=12.0, checked_at="2026-05-20T06:00:00+00:00")
        repo.save(r)

        last = repo.last_by_summit()
        assert len(last) == 1
        assert last[0].calm_hours == (8, 9)
