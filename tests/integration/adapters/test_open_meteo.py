import pytest
import respx
from httpx import Response

from paralert.adapters.weather.open_meteo import BASE_URL, OpenMeteoWeather

FAKE_RESPONSE = {
    "hourly": {
        "time": ["2026-05-20T00:00", "2026-05-20T01:00", "2026-05-20T02:00"],
        "windspeed_800hPa": [10.0, 12.5, 8.0],
        "windspeed_700hPa": [14.0, 16.0, 11.0],
    }
}


@pytest.mark.anyio
@respx.mock
async def test_fetch_wind_parses_response():
    respx.get(BASE_URL).mock(return_value=Response(200, json=FAKE_RESPONSE))

    weather = OpenMeteoWeather()
    result = await weather.fetch_wind(lat=45.0, lon=5.0, altitudes_m=(2000, 3000))

    assert 2000 in result.hourly
    assert 3000 in result.hourly
    assert result.hourly[2000]["2026-05-20T00:00"] == 10.0
    assert result.hourly[3000]["2026-05-20T01:00"] == 16.0


@pytest.mark.anyio
@respx.mock
async def test_fetch_wind_ignores_unknown_altitude():
    respx.get(BASE_URL).mock(return_value=Response(200, json={
        "hourly": {"time": ["2026-05-20T00:00"], "windspeed_800hPa": [10.0]}
    }))

    result = await OpenMeteoWeather().fetch_wind(lat=45.0, lon=5.0, altitudes_m=(2000,))
    assert 2000 in result.hourly
    assert 9999 not in result.hourly
