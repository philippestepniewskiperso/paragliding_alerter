from dataclasses import dataclass


@dataclass(frozen=True)
class Summit:
    id: int | None
    name: str
    lat: float
    lon: float
    altitudes_m: tuple[int, ...]
    enabled: bool = True


@dataclass(frozen=True)
class Settings:
    ntfy_url: str
    ntfy_topic: str
    wind_calm_kmh: float
    cron_expression: str


@dataclass(frozen=True)
class WindData:
    # {altitude_m: {iso_datetime: speed_kmh}}  e.g. {"2026-05-20T08:00": 12.5}
    hourly: dict[int, dict[str, float]]


@dataclass(frozen=True)
class CheckResult:
    summit_id: int
    target_date: str          # "YYYY-MM-DD"
    calm_hours: tuple[int, ...]  # UTC hours where all altitudes are calm
    max_wind_kmh: float
    checked_at: str           # ISO8601
