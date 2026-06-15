from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlotConfig:
    start_hour: int  # heure locale (0–23)
    end_hour: int    # heure locale (1–24), end_hour > start_hour


@dataclass(frozen=True)
class Summit:
    id: int | None
    name: str
    lat: float
    lon: float
    altitudes_m: tuple[int, ...]
    enabled: bool = True
    custom_slots: tuple[SlotConfig, ...] | None = None  # None = hérite des globaux
    meteociel_url: str | None = None  # page "tendances haute altitude" — fallback si open-meteo down


@dataclass(frozen=True)
class Settings:
    ntfy_url: str
    ntfy_topic: str
    wind_calm_kmh: float
    cron_expression: str
    season_start: str  # "MM-DD"
    season_end: str  # "MM-DD"
    require_no_snow: bool
    only_off_peak: bool
    timezone: str  # e.g. "Europe/Paris"
    cloud_cover_max_pct: float  # 0–100
    custom_slots: tuple[SlotConfig, ...] = field(default_factory=tuple)  # vide = fallback 3h auto


@dataclass(frozen=True)
class WindHour:
    speed_kmh: float
    direction_deg: float


@dataclass(frozen=True)
class SurfaceHour:
    cloud_cover_pct: float
    precipitation_mm: float
    snow_depth_m: float


@dataclass(frozen=True)
class WindData:
    # {altitude_m: {iso_datetime: WindHour}}
    hourly: dict[int, dict[str, WindHour]]
    # {iso_datetime: SurfaceHour}
    surface: dict[str, SurfaceHour]
    source: str = "open-meteo"  # data provider: "open-meteo" | "meteociel"


@dataclass(frozen=True)
class WindSlot:
    altitude_m: int
    mean_speed_kmh: float
    max_speed_kmh: float
    mean_direction_deg: float


@dataclass(frozen=True)
class CalmSlot:
    start_hour: int  # UTC (0, 3, 6, …, 21)
    end_hour: int  # UTC exclusive (3, 6, …, 24)
    wind_by_altitude: tuple[WindSlot, ...]
    is_calm: bool = True
    calm_ceiling_m: int | None = None  # highest alt in contiguous calm prefix from lowest; None if not calm


@dataclass(frozen=True)
class CheckResult:
    summit_id: int
    target_date: str  # "YYYY-MM-DD"
    calm_slots: tuple[CalmSlot, ...]
    max_wind_kmh: float  # max across all hours and altitudes
    checked_at: str  # ISO8601
    all_slots: tuple[CalmSlot, ...] = field(default_factory=tuple)
    source: str = "open-meteo"  # data provider used for this result
