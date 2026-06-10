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


def _date_label(date: str, checked_at_day: str) -> str:
    check_d = _date_cls.fromisoformat(checked_at_day)
    target_d = _date_cls.fromisoformat(date)
    diff = (target_d - check_d).days
    if diff == 0:
        return "Aujourd'hui"
    if diff == 1:
        return "Demain"
    return f"Dans {diff} jours ({date})"


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

        lines: list[str] = []
        for date in sorted(by_date.keys()):
            day_results = by_date[date]
            total_slots = sum(len(r.calm_slots) for r in day_results)
            label = _date_label(date, checked_at_day)
            lines.append(f"📅 {label} — {total_slots} créneau(x) calme(s)\n")

            for r in day_results:
                summit = summit_by_id.get(r.summit_id)
                summit_name = summit.name if summit else f"#{r.summit_id}"
                lines.append(f"⛰  {summit_name}")

                for slot in r.calm_slots:
                    hours_local = _slot_hours_local(
                        slot.start_hour, slot.end_hour, date, tz
                    )
                    lines.append(f"  🕐 {hours_local} (heure locale)")
                    for w in slot.wind_by_altitude:
                        arrow = _wind_arrow(w.mean_direction_deg)
                        card = _deg_to_cardinal(w.mean_direction_deg)
                        lines.append(
                            f"    {w.altitude_m}m  moy {w.mean_speed_kmh:.0f} · max {w.max_speed_kmh:.0f} km/h  {arrow}{card}"
                        )

                if summit:
                    lines.append(
                        f"  🔗 https://www.windy.com/?{summit.lat},{summit.lon},10"
                    )
                lines.append("")

        body = "\n".join(lines).rstrip()

        live_settings: Settings = self._settings_fn()
        url = f"{live_settings.ntfy_url.rstrip('/')}/{live_settings.ntfy_topic}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                content=body.encode(),
                headers={
                    "Title": "Paralert — créneaux calmes",
                    "Priority": "default",
                    "Tags": "paragliding,wind",
                },
            )
