from pydantic import BaseModel, Field, model_validator


class SlotConfigSchema(BaseModel):
    start_hour: int = Field(ge=0, lt=24)
    end_hour: int = Field(gt=0, le=24)

    @model_validator(mode="after")
    def end_after_start(self) -> "SlotConfigSchema":
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be greater than start_hour")
        return self


class SummitCreate(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitudes_m: list[int] = Field(min_length=1)
    enabled: bool = True
    custom_slots: list[SlotConfigSchema] | None = None


class SummitRead(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    altitudes_m: list[int]
    enabled: bool
    custom_slots: list[SlotConfigSchema] | None = None


class SummitUpdate(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitudes_m: list[int] = Field(min_length=1)
    enabled: bool
    custom_slots: list[SlotConfigSchema] | None = None


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
    custom_slots: list[SlotConfigSchema] = []


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
    custom_slots: list[SlotConfigSchema] = []


class WindSlotRead(BaseModel):
    altitude_m: int
    mean_speed_kmh: float
    max_speed_kmh: float
    mean_direction_deg: float


class CalmSlotRead(BaseModel):
    start_hour: int
    end_hour: int
    wind_by_altitude: list[WindSlotRead]
    is_calm: bool = True


class CheckResultRead(BaseModel):
    summit_id: int
    target_date: str
    calm_slots: list[CalmSlotRead]
    max_wind_kmh: float
    checked_at: str
    all_slots: list[CalmSlotRead] = []
