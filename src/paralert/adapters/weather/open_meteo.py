import httpx

from paralert.domain.models import SurfaceHour, WindData, WindHour
from paralert.domain.ports import WeatherPort

_ALTITUDE_TO_HPA: dict[int, int] = {2000: 800, 3000: 700, 4000: 600}
BASE_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoWeather(WeatherPort):
    async def fetch_wind(self, lat: float, lon: float, altitudes_m: tuple[int, ...]) -> WindData:
        levels = [_ALTITUDE_TO_HPA[a] for a in altitudes_m if a in _ALTITUDE_TO_HPA]
        hourly_fields = [f for hpa in levels for f in (f"windspeed_{hpa}hPa", f"winddirection_{hpa}hPa")]
        hourly_fields += ["cloudcover", "precipitation", "snow_depth"]

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_fields),
            "forecast_days": 7,
            "wind_speed_unit": "kmh",
            "timezone": "UTC",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        times: list[str] = data["hourly"]["time"]
        hourly: dict[int, dict[str, WindHour]] = {}

        for altitude in altitudes_m:
            hpa = _ALTITUDE_TO_HPA.get(altitude)
            if hpa is None:
                continue
            speeds: list[float] = data["hourly"][f"windspeed_{hpa}hPa"]
            directions: list[float] = data["hourly"][f"winddirection_{hpa}hPa"]
            hourly[altitude] = {
                t: WindHour(speed_kmh=s, direction_deg=d)
                for t, s, d in zip(times, speeds, directions)
                if s is not None and d is not None
            }

        cloud_covers: list[float] = data["hourly"]["cloudcover"]
        precipitations: list[float] = data["hourly"]["precipitation"]
        snow_depths: list[float] = data["hourly"]["snow_depth"]

        surface: dict[str, SurfaceHour] = {
            t: SurfaceHour(
                cloud_cover_pct=cc if cc is not None else 0.0,
                precipitation_mm=pr if pr is not None else 0.0,
                snow_depth_m=sd if sd is not None else 0.0,
            )
            for t, cc, pr, sd in zip(times, cloud_covers, precipitations, snow_depths)
        }

        return WindData(hourly=hourly, surface=surface)
