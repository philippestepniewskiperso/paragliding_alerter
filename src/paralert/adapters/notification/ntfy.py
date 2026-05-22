import httpx

from paralert.domain.models import CheckResult, Settings, Summit
from paralert.domain.ports import NotificationPort


_CARDINALS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


def _deg_to_cardinal(deg: float) -> str:
    return _CARDINALS[round(deg / 45) % 8]


class NtfyNotifier(NotificationPort):
    def __init__(self, settings_fn):
        self._settings_fn = settings_fn

    async def send(self, summit: Summit, result: CheckResult) -> None:
        settings: Settings = self._settings_fn()

        if not result.calm_slots:
            return

        now_date = result.checked_at[:10]
        date_label = "Aujourd'hui" if result.target_date == now_date else "Demain"
        windy_url = f"https://www.windy.com/?{summit.lat},{summit.lon},10"

        lines = [
            f"{date_label} ({result.target_date}) — {len(result.calm_slots)} créneau(x) calme(s)\n"
        ]
        for slot in result.calm_slots:
            lines.append(f"  {slot.start_hour:02d}h–{slot.end_hour:02d}h UTC")
            for w in slot.wind_by_altitude:
                card = _deg_to_cardinal(w.mean_direction_deg)
                lines.append(
                    f"    {w.altitude_m}m : moy {w.mean_speed_kmh:.0f} km/h · max {w.max_speed_kmh:.0f} km/h · {card}"
                )

        lines.append(f"\n{windy_url}")
        body = "\n".join(lines)

        url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                content=body.encode(),
                headers={
                    "Title": f"{summit.name} - conditions calmes",
                    "Priority": "default",
                    "Tags": "paragliding,wind",
                    "Click": windy_url,
                },
            )
