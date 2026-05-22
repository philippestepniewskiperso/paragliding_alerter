import pytest

from paralert.domain.models import SurfaceHour, WindData, WindHour
from paralert.domain.services import find_calm_slots, max_wind_on_date

DATE = "2026-05-20"
_EMPTY_SURFACE: dict = {}


def _wind(speeds_by_altitude: dict[int, dict[int, float]], direction: float = 45.0) -> WindData:
    """Build WindData from {altitude: {hour: speed}} shorthand."""
    return WindData(
        hourly={
            alt: {
                f"{DATE}T{h:02d}:00": WindHour(speed_kmh=spd, direction_deg=direction)
                for h, spd in hours.items()
            }
            for alt, hours in speeds_by_altitude.items()
        },
        surface=_EMPTY_SURFACE,
    )


def _all_hours(speed: float, direction: float = 45.0) -> dict[int, float]:
    return {h: speed for h in range(24)}


def test_all_calm_returns_all_slots():
    wind = _wind({2000: _all_hours(10.0), 3000: _all_hours(8.0)})
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    assert len(slots) == 8  # 24h / 3h = 8 slots


def test_calm_slot_boundaries():
    wind = _wind({2000: _all_hours(10.0)})
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    assert slots[0].start_hour == 0
    assert slots[0].end_hour == 3
    assert slots[-1].start_hour == 21
    assert slots[-1].end_hour == 24


def test_windy_slot_excluded():
    # slot 0-3 is windy, rest calm
    hours = {h: (30.0 if h < 3 else 10.0) for h in range(24)}
    wind = _wind({2000: hours})
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    assert all(s.start_hour >= 3 for s in slots)


def test_one_altitude_windy_excludes_slot():
    # 3000m is windy in slot 0-3
    wind = _wind({2000: _all_hours(10.0), 3000: {h: (20.0 if h < 3 else 8.0) for h in range(24)}})
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    assert all(s.start_hour >= 3 for s in slots)


def test_no_calm_slots():
    wind = _wind({2000: _all_hours(50.0)})
    assert find_calm_slots(wind, threshold_kmh=15, date=DATE) == ()


def test_wind_slot_stats():
    hours = {0: 10.0, 1: 12.0, 2: 14.0}
    wind = _wind({2000: hours}, direction=90.0)
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    w = slots[0].wind_by_altitude[0]
    assert w.mean_speed_kmh == pytest.approx(12.0)
    assert w.max_speed_kmh == pytest.approx(14.0)
    assert w.mean_direction_deg == pytest.approx(90.0)


def test_filters_other_date():
    other = "2026-05-21"
    wind = WindData(
        hourly={2000: {f"{other}T{h:02d}:00": WindHour(5.0, 0.0) for h in range(24)}},
        surface=_EMPTY_SURFACE,
    )
    assert find_calm_slots(wind, threshold_kmh=15, date=DATE) == ()


def test_max_wind_on_date():
    wind = _wind({2000: {8: 10.0, 9: 20.0}, 3000: {8: 5.0, 9: 18.0}})
    assert max_wind_on_date(wind, DATE) == 20.0


def test_max_wind_no_data():
    wind = _wind({2000: {}})
    assert max_wind_on_date(wind, DATE) == 0.0


def test_sunlight_filter_excludes_night_slots():
    wind = _wind({2000: _all_hours(10.0)})
    # sunrise=6, sunset=20 → slots fully within [6,20]: 6-9,9-12,12-15,15-18,18-21... wait 18-21 end=21 > 20 excluded
    # slots: 6-9, 9-12, 12-15, 15-18 = 4 slots
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE, sunrise_utc=6, sunset_utc=20)
    assert all(s.start_hour >= 6 for s in slots)
    assert all(s.end_hour <= 20 for s in slots)


def test_cloud_filter_excludes_cloudy_slots():
    surface = {
        f"{DATE}T{h:02d}:00": SurfaceHour(cloud_cover_pct=80.0 if h < 6 else 20.0, precipitation_mm=0.0, snow_depth_m=0.0)
        for h in range(24)
    }
    wind = WindData(hourly={2000: {f"{DATE}T{h:02d}:00": WindHour(10.0, 45.0) for h in range(24)}}, surface=surface)
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE, cloud_cover_max_pct=50.0)
    assert all(s.start_hour >= 6 for s in slots)


def test_precipitation_filter_excludes_rainy_slots():
    surface = {
        f"{DATE}T{h:02d}:00": SurfaceHour(cloud_cover_pct=0.0, precipitation_mm=1.0 if h < 3 else 0.0, snow_depth_m=0.0)
        for h in range(24)
    }
    wind = WindData(hourly={2000: {f"{DATE}T{h:02d}:00": WindHour(10.0, 45.0) for h in range(24)}}, surface=surface)
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE)
    assert all(s.start_hour >= 3 for s in slots)


def test_snow_filter_excludes_snowy_slots():
    surface = {
        f"{DATE}T{h:02d}:00": SurfaceHour(cloud_cover_pct=0.0, precipitation_mm=0.0, snow_depth_m=0.1)
        for h in range(24)
    }
    wind = WindData(hourly={2000: {f"{DATE}T{h:02d}:00": WindHour(10.0, 45.0) for h in range(24)}}, surface=surface)
    assert find_calm_slots(wind, threshold_kmh=15, date=DATE, require_no_snow=True) == ()


def test_off_peak_filter():
    wind = _wind({2000: _all_hours(10.0)})
    # off-peak: end before 10 UTC or start after 15 UTC
    slots = find_calm_slots(wind, threshold_kmh=15, date=DATE, only_off_peak=True, off_peak_end_utc=10, off_peak_start_utc=15)
    for s in slots:
        assert s.end_hour <= 10 or s.start_hour >= 15
