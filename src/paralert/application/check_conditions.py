import logging
from datetime import datetime, timedelta, timezone

import httpx
from zoneinfo import ZoneInfo

from paralert.domain.models import CheckResult, SlotConfig

_log = logging.getLogger(__name__)
from paralert.domain.ports import (
    CheckResultRepository,
    NotificationPort,
    SettingsRepository,
    SummitRepository,
    WeatherPort,
)
from paralert.domain.services import (
    find_all_slots,
    find_calm_slots,
    max_wind_on_date,
    sunrise_sunset_utc,
)


class CheckConditionsUseCase:
    def __init__(
        self,
        weather: WeatherPort,
        summits: SummitRepository,
        settings: SettingsRepository,
        results: CheckResultRepository,
        notifier: NotificationPort,
    ):
        self._weather = weather
        self._summits = summits
        self._settings = settings
        self._results = results
        self._notifier = notifier

    async def execute(self) -> list[CheckResult]:
        settings = self._settings.get()
        now = datetime.now(timezone.utc)
        dates = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        checked_at = now.isoformat()

        all_results: list[CheckResult] = []
        all_summits = self._summits.list(enabled_only=True)

        for summit in all_summits:
            try:
                wind_data = await self._weather.fetch_wind(
                    summit.lat, summit.lon, summit.altitudes_m
                )
            except httpx.HTTPError as exc:
                _log.warning("fetch_wind failed for summit %s (%s): %s", summit.id, summit.name, exc)
                continue

            # Résolution créneaux: sommet > global > fallback auto
            effective_slots = summit.custom_slots if summit.custom_slots is not None else settings.custom_slots

            for date in dates:
                if not _in_season(date, settings.season_start, settings.season_end):
                    continue

                sunrise, sunset = sunrise_sunset_utc(summit.lat, summit.lon, date)
                off_peak_end, off_peak_start = _local_to_utc(
                    12, 17, date, settings.timezone
                )

                custom_slots_utc: tuple[tuple[int, int], ...] | None = None
                if effective_slots:
                    custom_slots_utc = tuple(
                        _slot_local_to_utc(sc, date, settings.timezone)
                        for sc in effective_slots
                    )

                calm_slots = find_calm_slots(
                    wind_data,
                    settings.wind_calm_kmh,
                    date,
                    sunrise_utc=sunrise,
                    sunset_utc=sunset,
                    require_no_snow=settings.require_no_snow,
                    only_off_peak=settings.only_off_peak,
                    off_peak_end_utc=off_peak_end,
                    off_peak_start_utc=off_peak_start,
                    cloud_cover_max_pct=settings.cloud_cover_max_pct,
                    custom_slots_utc=custom_slots_utc,
                )

                all_slots = find_all_slots(
                    wind_data,
                    settings.wind_calm_kmh,
                    date,
                    sunrise_utc=sunrise,
                    sunset_utc=sunset,
                    require_no_snow=settings.require_no_snow,
                    only_off_peak=settings.only_off_peak,
                    off_peak_end_utc=off_peak_end,
                    off_peak_start_utc=off_peak_start,
                    cloud_cover_max_pct=settings.cloud_cover_max_pct,
                    custom_slots_utc=custom_slots_utc,
                )

                # Drop slots already past when checking today
                if date == now.strftime("%Y-%m-%d"):
                    calm_slots = tuple(s for s in calm_slots if s.end_hour > now.hour)
                    all_slots = tuple(s for s in all_slots if s.end_hour > now.hour)
                max_wind = max_wind_on_date(wind_data, date)

                result = CheckResult(
                    summit_id=summit.id,  # type: ignore[arg-type]
                    target_date=date,
                    calm_slots=calm_slots,
                    max_wind_kmh=max_wind,
                    checked_at=checked_at,
                    all_slots=all_slots,
                )
                self._results.save(result)
                all_results.append(result)

        if any(r.calm_slots for r in all_results):
            await self._notifier.send_summary(all_results, all_summits, settings)

        return all_results


def _in_season(date: str, season_start: str, season_end: str) -> bool:
    """Check if date (YYYY-MM-DD) falls within [season_start, season_end] (MM-DD, inclusive)."""
    month_day = date[5:]  # "MM-DD"
    if season_start <= season_end:
        return season_start <= month_day <= season_end
    # wraps around year-end (not our case but handle it)
    return month_day >= season_start or month_day <= season_end


def _local_to_utc(
    hour_end_local: int, hour_start_local: int, date: str, tz_name: str
) -> tuple[int, int]:
    """Convert local hours to UTC hours for the given date."""
    tz = ZoneInfo(tz_name)
    naive_end = datetime.fromisoformat(f"{date}T{hour_end_local:02d}:00:00")
    naive_start = datetime.fromisoformat(f"{date}T{hour_start_local:02d}:00:00")
    utc_end = naive_end.replace(tzinfo=tz).astimezone(timezone.utc).hour
    utc_start = naive_start.replace(tzinfo=tz).astimezone(timezone.utc).hour
    return utc_end, utc_start


def _slot_local_to_utc(sc: SlotConfig, date: str, tz_name: str) -> tuple[int, int]:
    """Convert a SlotConfig (local hours) to a (start_utc, end_utc) tuple.
    Preserves duration: end_utc = start_utc + (end_hour - start_hour).
    Handles end_hour=24 (midnight) by avoiding datetime(hour=24).
    """
    tz = ZoneInfo(tz_name)
    naive_start = datetime.fromisoformat(f"{date}T{sc.start_hour:02d}:00:00")
    utc_start = naive_start.replace(tzinfo=tz).astimezone(timezone.utc).hour
    utc_end = utc_start + (sc.end_hour - sc.start_hour)
    return utc_start, utc_end
