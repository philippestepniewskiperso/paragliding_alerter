"""Composite weather adapter: primary source, with a fallback on HTTP failure.

Tries the primary (open-meteo) first. If it raises an HTTP error and the summit
carries a meteociel URL, retries against the fallback (meteociel). Without a
meteociel URL the primary error propagates unchanged.
"""

import logging

import httpx

from paralert.domain.models import WindData
from paralert.domain.ports import WeatherPort

_log = logging.getLogger(__name__)


class FallbackWeather(WeatherPort):
    def __init__(self, primary: WeatherPort, fallback: WeatherPort):
        self._primary = primary
        self._fallback = fallback

    async def fetch_wind(
        self,
        lat: float,
        lon: float,
        altitudes_m: tuple[int, ...],
        *,
        meteociel_url: str | None = None,
    ) -> WindData:
        try:
            return await self._primary.fetch_wind(
                lat, lon, altitudes_m, meteociel_url=meteociel_url
            )
        except httpx.HTTPError as exc:
            if not meteociel_url:
                raise
            _log.warning(
                "primary weather failed (%s); falling back to meteociel %s",
                exc, meteociel_url,
            )
            return await self._fallback.fetch_wind(
                lat, lon, altitudes_m, meteociel_url=meteociel_url
            )
