from datetime import datetime, timedelta, timezone

from paralert.domain.models import CheckResult
from paralert.domain.ports import (
    CheckResultRepository,
    NotificationPort,
    SettingsRepository,
    SummitRepository,
    WeatherPort,
)
from paralert.domain.services import find_calm_hours, max_wind_on_date


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
        dates = [now.strftime("%Y-%m-%d"), (now + timedelta(days=1)).strftime("%Y-%m-%d")]
        checked_at = now.isoformat()

        all_results: list[CheckResult] = []

        for summit in self._summits.list(enabled_only=True):
            wind_data = await self._weather.fetch_wind(summit.lat, summit.lon, summit.altitudes_m)

            for date in dates:
                calm_hours = find_calm_hours(wind_data, settings.wind_calm_kmh, date)
                max_wind = max_wind_on_date(wind_data, date)

                result = CheckResult(
                    summit_id=summit.id,
                    target_date=date,
                    calm_hours=calm_hours,
                    max_wind_kmh=max_wind,
                    checked_at=checked_at,
                )
                self._results.save(result)
                all_results.append(result)

                if calm_hours:
                    await self._notifier.send(summit, result)

        return all_results
