"""Adapter scraping meteociel.fr "tendances haute altitude" pages.

Used as a fallback when open-meteo is unreachable. Each summit must carry the
URL of its meteociel page (no generic lat/lon → station mapping exists).

The page is a 6-hourly GFS table. Wind columns are: 2m, z850, z800, z700,
z600, z500. We map the app's altitudes to the nearest pressure level. The
table carries no cloud-cover nor snow-depth, so those surface fields are
neutralised (cloud=0 %, snow=0) and only precipitation is read.
"""

import re
from datetime import date as date_cls, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from paralert.domain.models import SurfaceHour, WindData, WindHour
from paralert.domain.ports import WeatherPort

# requested altitude (m) → index into the 6 wind columns (2m, z850, z800, z700, z600, z500)
_ALT_TO_WIND_IDX: dict[int, int] = {0: 0, 1000: 1, 2000: 2, 3000: 3, 4000: 4}

_ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DEG_RE = re.compile(r":\s*(-?\d+)\s*°")
_DAY_RE = re.compile(r"(?:Lun|Mar|Mer|Jeu|Ven|Sam|Dim)\D*?(\d{1,2})", re.S | re.I)

# column layout, relative to the "Heure" cell (base):
#   base+0 heure | base+1..6 temp(6) | base+7..11 geopot(5) | base+12..17 vent(6) | base+18 préci
_WIND_OFFSET = 12
_PRECIP_OFFSET = 18
_MIN_CELLS_AFTER_BASE = 19


def _strip(html: str) -> str:
    return _TAG_RE.sub("", html).strip()


def _resolve_date(cursor: date_cls, day: int) -> date_cls:
    """Advance cursor forward (max 40 days) until cursor.day == day."""
    for _ in range(40):
        if cursor.day == day:
            return cursor
        cursor += timedelta(days=1)
    return cursor


def parse_meteociel_html(
    html: str,
    altitudes_m: tuple[int, ...],
    *,
    tz: ZoneInfo,
    reference_date: date_cls,
) -> WindData:
    """Parse a meteociel "tendances haute altitude" page into WindData.

    Times on the page are local (``tz``); keys in the result are UTC, matching
    the ``{YYYY-MM-DDTHH:00}`` format the domain expects.
    """
    wanted = [(a, _ALT_TO_WIND_IDX[a]) for a in altitudes_m if a in _ALT_TO_WIND_IDX]

    hourly: dict[int, dict[str, WindHour]] = {a: {} for a, _ in wanted}
    surface: dict[str, SurfaceHour] = {}

    current_date: date_cls | None = None

    for row_html in _ROW_RE.findall(html):
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 2:
            continue
        stripped = [_strip(c) for c in cells]

        heure_idx = next((i for i, s in enumerate(stripped) if _TIME_RE.match(s)), None)
        if heure_idx is None:
            continue
        base = heure_idx
        if base + _MIN_CELLS_AFTER_BASE > len(cells):
            continue

        # day cell precedes the heure cell (only on the first row of each day)
        if base >= 1:
            day_match = _DAY_RE.search(cells[base - 1])
            if day_match:
                day = int(day_match.group(1))
                start = current_date or reference_date
                current_date = _resolve_date(start, day)
        if current_date is None:
            continue

        hour = int(_TIME_RE.match(stripped[base]).group(1))
        local_dt = datetime(current_date.year, current_date.month, current_date.day, hour, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)
        key = utc_dt.strftime("%Y-%m-%dT%H:00")

        # wind per requested altitude
        for alt, idx in wanted:
            raw = cells[base + _WIND_OFFSET + idx]
            speed_txt = _strip(raw).replace(",", ".")
            deg_match = _DEG_RE.search(raw)
            try:
                speed = float(speed_txt)
            except ValueError:
                continue
            direction = float(deg_match.group(1)) % 360 if deg_match else 0.0
            hourly[alt][key] = WindHour(speed_kmh=speed, direction_deg=direction)

        # precipitation; cloud & snow unavailable → neutralised
        precip_txt = stripped[base + _PRECIP_OFFSET].replace(",", ".")
        try:
            precip = float(precip_txt)
        except ValueError:
            precip = 0.0
        surface[key] = SurfaceHour(cloud_cover_pct=0.0, precipitation_mm=precip, snow_depth_m=0.0)

    return WindData(hourly=hourly, surface=surface, source="meteociel")


class MeteoCielWeather(WeatherPort):
    def __init__(self, tz: str = "Europe/Paris"):
        self._tz = ZoneInfo(tz)

    async def fetch_wind(
        self,
        lat: float,
        lon: float,
        altitudes_m: tuple[int, ...],
        *,
        meteociel_url: str | None = None,
    ) -> WindData:
        if not meteociel_url:
            raise ValueError("meteociel_url is required for MeteoCielWeather")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(meteociel_url, headers=headers)
            response.raise_for_status()
            html = response.content.decode("iso-8859-1", errors="replace")

        today_local = datetime.now(self._tz).date()
        return parse_meteociel_html(
            html, altitudes_m, tz=self._tz, reference_date=today_local
        )
