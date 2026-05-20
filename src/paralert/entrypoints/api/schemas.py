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


class AppSettingsUpdate(BaseModel):
    ntfy_url: str
    ntfy_topic: str
    wind_calm_kmh: float = Field(gt=0, le=200)
    cron_expression: str


class CheckResultRead(BaseModel):
    summit_id: int
    target_date: str
    calm_hours: list[int]
    max_wind_kmh: float
    checked_at: str
