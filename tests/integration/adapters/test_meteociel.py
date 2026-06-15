from datetime import date
from zoneinfo import ZoneInfo

import pytest
import respx
from httpx import Response

from paralert.adapters.weather.meteociel import (
    MeteoCielWeather,
    parse_meteociel_html,
)

TZ = ZoneInfo("Europe/Paris")


def _wind_cell(direction_label: str, deg: int, speed: str) -> str:
    return (
        f"<td align=\"center\"><img src='//x/vent/x.png' "
        f"alt='{direction_label} : {deg} °' title='{direction_label} : {deg} °'> {speed}</td>"
    )


def _temps() -> str:
    return "".join(f"<td>{v}</td>" for v in (20.1, 15.9, 12.3, 6.1, -2.2, -12.1))


def _geopot() -> str:
    return "".join(f"<td>{v}</td>" for v in (152, 203, 314, 438, 580))


def _winds(speeds) -> str:
    # 2m, z850, z800, z700, z600, z500
    labels = [("Nord", 0)] * 6
    return "".join(_wind_cell(l, d, str(s)) for (l, d), s in zip(labels, speeds))


def _row(day_cell: str, heure: str, speeds, precip: str) -> str:
    return (
        "<tr>"
        f"{day_cell}"
        f"<td>{heure}</td>"
        f"{_temps()}{_geopot()}"
        f"{_winds(speeds)}"
        f"<td>{precip}</td><td>1013</td><td>567</td><td>4042</td>"
        "</tr>"
    )


# row1 Dim 14 20:00 (day cell) | row2 Lun 15 02:00 (new day, day cell) |
# row3 Lun 15 08:00 (continuation, no day cell)
FIXTURE = (
    "<table><tr><td>z500</td></tr>"
    + _row("<td rowspan=1>Dim<br>14<br></td>", "20:00", [5, 10, 20, 15, 20, 30], "--")
    + _row("<td rowspan=4>Lun<br>15<br></td>", "02:00", [3, 8, 12, 9, 14, 22], "1,5")
    + _row("", "08:00", [4, 9, 13, 10, 15, 23], "0")
    + "</table>"
)


def test_parse_maps_altitudes_and_converts_to_utc():
    wd = parse_meteociel_html(
        FIXTURE, (0, 2000, 3000, 4000), tz=TZ, reference_date=date(2026, 6, 11)
    )

    # Dim 14 20:00 CEST -> 18:00 UTC
    assert wd.hourly[0]["2026-06-14T18:00"].speed_kmh == 5.0
    assert wd.hourly[2000]["2026-06-14T18:00"].speed_kmh == 20.0   # z800 column
    assert wd.hourly[3000]["2026-06-14T18:00"].speed_kmh == 15.0   # z700 column
    assert wd.hourly[4000]["2026-06-14T18:00"].speed_kmh == 20.0   # z600 column

    # new day Lun 15 02:00 CEST -> 00:00 UTC
    assert wd.hourly[0]["2026-06-15T00:00"].speed_kmh == 3.0
    # continuation row (no day cell) Lun 15 08:00 CEST -> 06:00 UTC
    assert wd.hourly[0]["2026-06-15T06:00"].speed_kmh == 4.0


def test_parse_surface_neutralises_cloud_and_snow_reads_precip():
    wd = parse_meteociel_html(
        FIXTURE, (0,), tz=TZ, reference_date=date(2026, 6, 11)
    )
    s0 = wd.surface["2026-06-14T18:00"]
    assert s0.cloud_cover_pct == 0.0
    assert s0.snow_depth_m == 0.0
    assert s0.precipitation_mm == 0.0          # "--" -> 0
    assert wd.surface["2026-06-15T00:00"].precipitation_mm == 1.5  # "1,5" -> 1.5


def test_parse_ignores_unmapped_altitude():
    wd = parse_meteociel_html(FIXTURE, (2000, 9999), tz=TZ, reference_date=date(2026, 6, 11))
    assert 2000 in wd.hourly
    assert 9999 not in wd.hourly


@pytest.mark.anyio
async def test_fetch_wind_requires_url():
    with pytest.raises(ValueError):
        await MeteoCielWeather().fetch_wind(45.0, 5.0, (2000,), meteociel_url=None)


@pytest.mark.anyio
@respx.mock
async def test_fetch_wind_decodes_and_parses():
    url = "https://www.meteociel.fr/tendances-haute-altitude/13375/lans.htm"
    respx.get(url).mock(
        return_value=Response(200, content=FIXTURE.encode("iso-8859-1"))
    )
    wd = await MeteoCielWeather().fetch_wind(45.0, 5.0, (2000,), meteociel_url=url)
    assert wd.hourly[2000]  # parsed at least one slot
