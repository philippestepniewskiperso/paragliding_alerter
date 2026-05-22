from pydantic import BaseModel, Field


class SummitCreate(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitudes_m: list[int] = Field(min_length=1)
    enabled: bool = True


class SummitRead(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    altitudes_m: list[int]
    enabled: bool


class SummitUpdate(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitudes_m: list[int] = Field(min_length=1)
    enabled: bool


class AppSettingsRead(BaseModel):
    ntfy_url: str
    ntfy_topic: str
    wind_calm_kmh: float
    cron_expression: str
    season_start: str
    season_end: str
    require_no_snow: bool
    only_off_peak: bool
    timezone: str
    cloud_cover_max_pct: float


class AppSettingsUpdate(BaseModel):
    ntfy_url: str
    ntfy_topic: str
    wind_calm_kmh: float = Field(gt=0, le=200)
    cron_expression: str
    season_start: str
    season_end: str
    require_no_snow: bool
    only_off_peak: bool
    timezone: str
    cloud_cover_max_pct: float = Field(ge=0, le=100)


class WindSlotRead(BaseModel):
    altitude_m: int
    mean_speed_kmh: float
    max_speed_kmh: float
    mean_direction_deg: float


class CalmSlotRead(BaseModel):
    start_hour: int
    end_hour: int
    wind_by_altitude: list[WindSlotRead]


class CheckResultRead(BaseModel):
    summit_id: int
    target_date: str
    calm_slots: list[CalmSlotRead]
    max_wind_kmh: float
    checked_at: str
