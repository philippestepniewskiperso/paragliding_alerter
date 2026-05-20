import pytest

from paralert.domain.models import WindData
from paralert.domain.services import find_calm_hours, max_wind_on_date

DATE = "2026-05-20"


def _wind(speeds_by_altitude: dict[int, dict[int, float]]) -> WindData:
    """Build WindData from {altitude: {hour: speed}} shorthand."""
    return WindData(
        hourly={
            alt: {f"{DATE}T{h:02d}:00": spd for h, spd in hours.items()}
            for alt, hours in speeds_by_altitude.items()
        }
    )


def test_all_calm():
    wind = _wind({2000: {8: 10.0, 9: 12.0}, 3000: {8: 8.0, 9: 11.0}})
    assert find_calm_hours(wind, threshold_kmh=15, date=DATE) == (8, 9)


def test_calm_only_at_low_altitude():
    # 3000m above threshold at hour 9 → not calm
    wind = _wind({2000: {8: 10.0, 9: 10.0}, 3000: {8: 8.0, 9: 20.0}})
    assert find_calm_hours(wind, threshold_kmh=15, date=DATE) == (8,)


def test_no_calm_hours():
    wind = _wind({2000: {8: 30.0}, 3000: {8: 25.0}})
    assert find_calm_hours(wind, threshold_kmh=15, date=DATE) == ()


def test_single_altitude():
    wind = _wind({2000: {10: 14.9, 11: 15.1}})
    assert find_calm_hours(wind, threshold_kmh=15, date=DATE) == (10,)


def test_filters_other_date():
    other = "2026-05-21"
    wind = WindData(hourly={2000: {f"{other}T08:00": 5.0}})
    assert find_calm_hours(wind, threshold_kmh=15, date=DATE) == ()


def test_max_wind_on_date():
    wind = _wind({2000: {8: 10.0, 9: 20.0}, 3000: {8: 5.0, 9: 18.0}})
    assert max_wind_on_date(wind, DATE) == 20.0


def test_max_wind_no_data():
    wind = _wind({2000: {}})
    assert max_wind_on_date(wind, DATE) == 0.0
