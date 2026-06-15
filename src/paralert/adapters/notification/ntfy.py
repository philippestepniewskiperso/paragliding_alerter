import os
from datetime import date as _date_cls, datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from paralert.domain.models import CheckResult, Settings, Summit
from paralert.domain.ports import NotificationPort


_CARDINALS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
_ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]


def _deg_to_cardinal(deg: float) -> str:
    return _CARDINALS[round(deg / 45) % 8]


def _wind_arrow(deg: float) -> str:
    return _ARROWS[round(deg / 45) % 8]


def _slot_hours_local(start_utc: int, end_utc: int, date: str, tz: ZoneInfo) -> str:
    def fmt(h: int) -> str:
        d = datetime(
            int(date[:4]), int(date[5:7]), int(date[8:10]), h, 0, 0, tzinfo=timezone.utc
        )
        local = d.astimezone(tz)
        return (
            f"{local.hour:02d}h{local.minute:02d}"
            if local.minute
            else f"{local.hour:02d}h"
        )

    return f"{fmt(start_utc)}–{fmt(end_utc)}"


_WEEKDAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _bold(text: str) -> str:
    """Render text with Unicode sans-serif bold glyphs.

    ntfy's phone apps don't render markdown, so we bold ASCII letters/digits
    directly; other chars (accents, spaces, punctuation) pass through unchanged.
    """
    out = []
    for ch in text:
        o = ord(ch)
        if "A" <= ch <= "Z":
            out.append(chr(0x1D5D4 + o - ord("A")))
        elif "a" <= ch <= "z":
            out.append(chr(0x1D5EE + o - ord("a")))
        elif "0" <= ch <= "9":
            out.append(chr(0x1D7EC + o - ord("0")))
        else:
            out.append(ch)
    return "".join(out)


def _date_label(date: str, checked_at_day: str) -> str:
    check_d = _date_cls.fromisoformat(checked_at_day)
    target_d = _date_cls.fromisoformat(date)
    diff = (target_d - check_d).days
    weekday = _WEEKDAYS_FR[target_d.weekday()]
    short = target_d.strftime("%d/%m")
    if diff == 0:
        rel = "aujourd'hui"
    elif diff == 1:
        rel = "demain"
    else:
        rel = f"dans {diff} jours"
    return f"{weekday} {short} ({rel})"


class NtfyNotifier(NotificationPort):
    def __init__(self, settings_fn):
        self._settings_fn = settings_fn

    async def send_summary(
        self,
        results: list[CheckResult],
        summits: list[Summit],
        settings: Settings,
    ) -> None:
        results_with_slots = [r for r in results if r.calm_slots]
        if not results_with_slots:
            return

        tz = ZoneInfo(settings.timezone)
        summit_by_id = {s.id: s for s in summits}
        checked_at_day = results_with_slots[0].checked_at[:10]

        by_date: dict[str, list[CheckResult]] = {}
        for r in results_with_slots:
            by_date.setdefault(r.target_date, []).append(r)

        def _link(summit: Summit | None) -> str | None:
            if summit and summit.meteociel_url:
                return summit.meteociel_url
            if summit:
                return f"https://www.windy.com/?{summit.lat},{summit.lon},10"
            return None

        click_url: str | None = None

        lines: list[str] = []
        for date in sorted(by_date.keys()):
            day_results = by_date[date]
            total_slots = sum(len(r.calm_slots) for r in day_results)
            label = _date_label(date, checked_at_day)

            if lines:
                lines.append("───────────────")
            lines.append(f"📅 {_bold(label)}  ·  {total_slots} créneau(x)")
            lines.append("")

            for r in day_results:
                summit = summit_by_id.get(r.summit_id)
                summit_name = summit.name if summit else f"#{r.summit_id}"
                src_label = "Meteociel" if r.source == "meteociel" else "Open-Meteo"
                lines.append(f"⛰️ {_bold(summit_name)}  ·  {src_label}")

                for slot in r.calm_slots:
                    hours_local = _slot_hours_local(
                        slot.start_hour, slot.end_hour, date, tz
                    )
                    if slot.wind_by_altitude and slot.calm_ceiling_m is not None:
                        min_alt = min(w.altitude_m for w in slot.wind_by_altitude)
                        flyable = (
                            f"volable à {slot.calm_ceiling_m}m"
                            if min_alt == slot.calm_ceiling_m
                            else f"volable {min_alt}→{slot.calm_ceiling_m}m"
                        )
                        lines.append(f"🕐 {hours_local}  ·  {flyable}")
                    else:
                        lines.append(f"🕐 {hours_local}")
                    for w in slot.wind_by_altitude:
                        arrow = _wind_arrow(w.mean_direction_deg)
                        card = _deg_to_cardinal(w.mean_direction_deg)
                        lines.append(
                            f"   {w.altitude_m:>4}m  {arrow}{card:<2}  "
                            f"{w.mean_speed_kmh:>2.0f} km/h (max {w.max_speed_kmh:.0f})"
                        )

                link = _link(summit)
                if link:
                    lines.append(f"🔗 {link}")
                    if click_url is None:
                        click_url = link
                lines.append("")

        body = "\n".join(lines).rstrip()

        live_settings: Settings = self._settings_fn()
        url = f"{live_settings.ntfy_url.rstrip('/')}/{live_settings.ntfy_topic}"
        headers = {
            # HTTP headers are latin-1 only; ntfy reads Title as UTF-8, so keep it
            # ASCII to avoid both an httpx encode error and mojibake on the device.
            "Title": "Paralert - creneaux calmes",
            "Priority": "default",
            "Tags": "paragliding,wind",
        }
        if click_url:
            headers["Click"] = click_url  # tap notification → open forecast
        base_url = os.getenv("PARALERT_BASE_URL", "").rstrip("/")
        if base_url:
            headers["Icon"] = f"{base_url}/static/favicon.png"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                content=body.encode(),
                headers=headers,
            )
