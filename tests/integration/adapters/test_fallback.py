import httpx
import pytest

from paralert.adapters.weather.fallback import FallbackWeather
from paralert.domain.models import WindData
from paralert.domain.ports import WeatherPort


class _Stub(WeatherPort):
    def __init__(self, *, raises=None, tag=""):
        self._raises = raises
        self._tag = tag
        self.calls: list[str | None] = []

    async def fetch_wind(self, lat, lon, altitudes_m, *, meteociel_url=None):
        self.calls.append(meteociel_url)
        if self._raises:
            raise self._raises
        return WindData(hourly={"tag": self._tag}, surface={})  # type: ignore[dict-item]


@pytest.mark.anyio
async def test_uses_primary_when_it_succeeds():
    primary = _Stub(tag="primary")
    fallback = _Stub(tag="fallback")
    wd = await FallbackWeather(primary, fallback).fetch_wind(
        45.0, 5.0, (2000,), meteociel_url="http://x"
    )
    assert wd.hourly["tag"] == "primary"
    assert fallback.calls == []


@pytest.mark.anyio
async def test_falls_back_on_http_error_when_url_present():
    primary = _Stub(raises=httpx.ConnectError("down"))
    fallback = _Stub(tag="fallback")
    wd = await FallbackWeather(primary, fallback).fetch_wind(
        45.0, 5.0, (2000,), meteociel_url="http://x"
    )
    assert wd.hourly["tag"] == "fallback"
    assert fallback.calls == ["http://x"]


@pytest.mark.anyio
async def test_reraises_when_no_url():
    primary = _Stub(raises=httpx.ConnectError("down"))
    fallback = _Stub(tag="fallback")
    with pytest.raises(httpx.ConnectError):
        await FallbackWeather(primary, fallback).fetch_wind(
            45.0, 5.0, (2000,), meteociel_url=None
        )
    assert fallback.calls == []
