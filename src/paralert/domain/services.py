import math
from datetime import date as date_type, timezone

from astral import LocationInfo
from astral.sun import sun

from .models import CalmSlot, WindData, WindSlot

SLOT_HOURS = 3


def sunrise_sunset_utc(lat: float, lon: float, date_str: str) -> tuple[int, int]:
    """Returns (sunrise_hour_utc, sunset_hour_utc) as integers (floored)."""
    d = date_type.fromisoformat(date_str)
    location = LocationInfo(latitude=lat, longitude=lon)
    s = sun(location.observer, date=d, tzinfo=timezone.utc)
    return s["sunrise"].hour, s["sunset"].hour


def find_calm_slots(
    wind_data: WindData,
    threshold_kmh: float,
    date: str,
    *,
    sunrise_utc: int | None = None,
    sunset_utc: int | None = None,
    require_no_snow: bool = False,
    only_off_peak: bool = False,
    off_peak_end_utc: int | None = None,
    off_peak_start_utc: int | None = None,
    cloud_cover_max_pct: float = 100.0,
    custom_slots_utc: tuple[tuple[int, int], ...] | None = None,
) -> tuple[CalmSlot, ...]:
    """Returns only calm slots (is_calm=True). See find_all_slots for all slots with is_calm flag."""
    return tuple(s for s in find_all_slots(
        wind_data, threshold_kmh, date,
        sunrise_utc=sunrise_utc, sunset_utc=sunset_utc,
        require_no_snow=require_no_snow, only_off_peak=only_off_peak,
        off_peak_end_utc=off_peak_end_utc, off_peak_start_utc=off_peak_start_utc,
        cloud_cover_max_pct=cloud_cover_max_pct, custom_slots_utc=custom_slots_utc,
    ) if s.is_calm)


def find_all_slots(
    wind_data: WindData,
    threshold_kmh: float,
    date: str,
    *,
    sunrise_utc: int | None = None,
    sunset_utc: int | None = None,
    require_no_snow: bool = False,
    only_off_peak: bool = False,
    off_peak_end_utc: int | None = None,
    off_peak_start_utc: int | None = None,
    cloud_cover_max_pct: float = 100.0,
    custom_slots_utc: tuple[tuple[int, int], ...] | None = None,
) -> tuple[CalmSlot, ...]:
    """
    Returns all configured slots that pass non-wind filters, each with is_calm set according
    to whether ALL hours at ALL altitudes have speed <= threshold.
    If custom_slots_utc is provided and non-empty, only those (start, end) windows are evaluated.
    Otherwise falls back to SLOT_HOURS-wide windows covering 00–24.
    """
    slots: list[CalmSlot] = []
    altitudes = list(wind_data.hourly.keys())

    windows: list[tuple[int, int]]
    if custom_slots_utc:
        windows = list(custom_slots_utc)
    else:
        windows = [(s, s + SLOT_HOURS) for s in range(0, 24, SLOT_HOURS)]

    for slot_start, slot_end in windows:
        slot_hours = list(range(slot_start, slot_end))

        # Filter: sunlight (entire slot must be in daylight)
        if sunrise_utc is not None and sunset_utc is not None:
            if slot_start < sunrise_utc or slot_end > sunset_utc:
                continue

        # Filter: cloud cover
        if cloud_cover_max_pct < 100.0:
            covers = [_surface_cloud(wind_data, date, h) for h in slot_hours]
            known_covers = [c for c in covers if c is not None]
            if known_covers and any(c > cloud_cover_max_pct for c in known_covers):
                continue

        # Filter: precipitation
        precips = [_surface_precip(wind_data, date, h) for h in slot_hours]
        known_precips = [p for p in precips if p is not None]
        if known_precips and any(p > 0 for p in known_precips):
            continue

        # Filter: snow
        if require_no_snow:
            snows = [_surface_snow(wind_data, date, h) for h in slot_hours]
            known_snows = [s for s in snows if s is not None]
            if known_snows and any(s > 0 for s in known_snows):
                continue

        # Filter: off-peak (slot ends before noon OR starts after evening)
        if only_off_peak and off_peak_end_utc is not None and off_peak_start_utc is not None:
            ends_before_noon = slot_end <= off_peak_end_utc
            starts_after_evening = slot_start >= off_peak_start_utc
            if not ends_before_noon and not starts_after_evening:
                continue

        wind_slots = tuple(
            WindSlot(
                altitude_m=alt,
                mean_speed_kmh=_mean([_hour_speed(wind_data, alt, date, h) for h in slot_hours]),
                max_speed_kmh=_max([_hour_speed(wind_data, alt, date, h) for h in slot_hours]),
                mean_direction_deg=_circular_mean([_hour_dir(wind_data, alt, date, h) for h in slot_hours]),
            )
            for alt in altitudes
        )

        # is_calm: contiguous calm prefix from lowest altitude
        calm_ceiling_m: int | None = None
        for alt in sorted(altitudes):
            known = [s for s in [_hour_speed(wind_data, alt, date, h) for h in slot_hours] if s is not None]
            if known and all(s <= threshold_kmh for s in known):
                calm_ceiling_m = alt
            else:
                break
        is_calm = calm_ceiling_m is not None

        slots.append(CalmSlot(start_hour=slot_start, end_hour=slot_end, wind_by_altitude=wind_slots, is_calm=is_calm, calm_ceiling_m=calm_ceiling_m))

    return tuple(slots)


def max_wind_on_date(wind_data: WindData, date: str) -> float:
    speeds = [
        wh.speed_kmh
        for hourly in wind_data.hourly.values()
        for dt, wh in hourly.items()
        if dt.startswith(date)
    ]
    return max(speeds) if speeds else 0.0


def _hour_speed(wind_data: WindData, alt: int, date: str, hour: int) -> float | None:
    key = f"{date}T{hour:02d}:00"
    wh = wind_data.hourly.get(alt, {}).get(key)
    return wh.speed_kmh if wh else None


def _hour_dir(wind_data: WindData, alt: int, date: str, hour: int) -> float | None:
    key = f"{date}T{hour:02d}:00"
    wh = wind_data.hourly.get(alt, {}).get(key)
    return wh.direction_deg if wh else None


def _surface_cloud(wind_data: WindData, date: str, hour: int) -> float | None:
    key = f"{date}T{hour:02d}:00"
    sh = wind_data.surface.get(key)
    return sh.cloud_cover_pct if sh else None


def _surface_precip(wind_data: WindData, date: str, hour: int) -> float | None:
    key = f"{date}T{hour:02d}:00"
    sh = wind_data.surface.get(key)
    return sh.precipitation_mm if sh else None


def _surface_snow(wind_data: WindData, date: str, hour: int) -> float | None:
    key = f"{date}T{hour:02d}:00"
    sh = wind_data.surface.get(key)
    return sh.snow_depth_m if sh else None


def _mean(values: list[float | None]) -> float:
    v = [x for x in values if x is not None]
    return sum(v) / len(v) if v else 0.0


def _max(values: list[float | None]) -> float:
    v = [x for x in values if x is not None]
    return max(v) if v else 0.0


def _circular_mean(degrees: list[float | None]) -> float:
    v = [d for d in degrees if d is not None]
    if not v:
        return 0.0
    sin_sum = sum(math.sin(math.radians(d)) for d in v)
    cos_sum = sum(math.cos(math.radians(d)) for d in v)
    return (math.degrees(math.atan2(sin_sum, cos_sum)) + 360) % 360
