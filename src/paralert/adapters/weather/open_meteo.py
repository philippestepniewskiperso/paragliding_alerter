import httpx

from paralert.domain.models import WindData
from paralert.domain.ports import WeatherPort

_ALTITUDE_TO_HPA: dict[int, int] = {2000: 800, 3000: 700, 4000: 600}
BASE_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoWeather(WeatherPort):
    async def fetch_wind(self, lat: float, lon: float, altitudes_m: tuple[int, ...]) -> WindData:
        levels = [_ALTITUDE_TO_HPA[a] for a in altitudes_m if a in _ALTITUDE_TO_HPA]
        hourly_params = ",".join(f"windspeed_{hpa}hPa" for hpa in levels)

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": hourly_params,
            "forecast_days": 2,
            "wind_speed_unit": "kmh",
            "timezone": "UTC",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        times: list[str] = data["hourly"]["time"]
        hourly: dict[int, dict[str, float]] = {}

        for altitude in altitudes_m:
            hpa = _ALTITUDE_TO_HPA.get(altitude)
            if hpa is None:
                continue
            key = f"windspeed_{hpa}hPa"
            speeds: list[float] = data["hourly"][key]
            hourly[altitude] = {t: s for t, s in zip(times, speeds) if s is not None}

        return WindData(hourly=hourly)
