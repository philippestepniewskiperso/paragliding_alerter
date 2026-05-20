import httpx

from paralert.domain.models import CheckResult, Settings, Summit
from paralert.domain.ports import NotificationPort


class NtfyNotifier(NotificationPort):
    def __init__(self, settings_fn):
        # settings_fn: callable() -> Settings (avoids circular dep at construction)
        self._settings_fn = settings_fn

    async def send(self, summit: Summit, result: CheckResult) -> None:
        settings: Settings = self._settings_fn()

        if not result.calm_hours:
            return

        hour_ranges = _format_hour_ranges(result.calm_hours)
        date_label = "Aujourd'hui" if result.target_date == result.checked_at[:10] else "Demain"
        altitudes_str = " / ".join(f"{a}m" for a in summit.altitudes_m)
        windy_url = f"https://www.windy.com/?{summit.lat},{summit.lon},10"

        body = (
            f"{date_label} ({result.target_date}) : {hour_ranges} UTC\n"
            f"Vent max : {result.max_wind_kmh:.0f} km/h\n"
            f"Altitudes surveillées : {altitudes_str}\n"
            f"{windy_url}"
        )

        url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                content=body.encode(),
                headers={
                    "Title": f"🪂 {summit.name} — conditions calmes",
                    "Priority": "default",
                    "Tags": "paragliding,wind",
                    "Click": windy_url,
                },
            )


def _format_hour_ranges(hours: tuple[int, ...]) -> str:
    """Compress consecutive hours: (8,9,10,14) -> '08h-11h, 14h'"""
    if not hours:
        return ""
    ranges: list[str] = []
    start = prev = hours[0]
    for h in hours[1:]:
        if h == prev + 1:
            prev = h
        else:
            ranges.append(f"{start:02d}h" if start == prev else f"{start:02d}h-{prev + 1:02d}h")
            start = prev = h
    ranges.append(f"{start:02d}h" if start == prev else f"{start:02d}h-{prev + 1:02d}h")
    return ", ".join(ranges)
