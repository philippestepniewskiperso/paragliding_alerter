from fastapi import APIRouter, Depends

from paralert.domain.models import Settings, SlotConfig
from paralert.domain.ports import SettingsRepository
from paralert.entrypoints.scheduler import reschedule

from .deps import get_settings_repo
from .schemas import AppSettingsRead, AppSettingsUpdate, SlotConfigSchema

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=AppSettingsRead)
def get_settings(repo: SettingsRepository = Depends(get_settings_repo)):
    s = repo.get()
    return AppSettingsRead(
        ntfy_url=s.ntfy_url,
        ntfy_topic=s.ntfy_topic,
        wind_calm_kmh=s.wind_calm_kmh,
        cron_expression=s.cron_expression,
        season_start=s.season_start,
        season_end=s.season_end,
        require_no_snow=s.require_no_snow,
        only_off_peak=s.only_off_peak,
        timezone=s.timezone,
        cloud_cover_max_pct=s.cloud_cover_max_pct,
        custom_slots=[SlotConfigSchema(start_hour=sc.start_hour, end_hour=sc.end_hour) for sc in s.custom_slots],
    )


@router.put("/", response_model=AppSettingsRead)
def update_settings(body: AppSettingsUpdate, repo: SettingsRepository = Depends(get_settings_repo)):
    settings = Settings(
        ntfy_url=body.ntfy_url,
        ntfy_topic=body.ntfy_topic,
        wind_calm_kmh=body.wind_calm_kmh,
        cron_expression=body.cron_expression,
        season_start=body.season_start,
        season_end=body.season_end,
        require_no_snow=body.require_no_snow,
        only_off_peak=body.only_off_peak,
        timezone=body.timezone,
        cloud_cover_max_pct=body.cloud_cover_max_pct,
        custom_slots=tuple(SlotConfig(start_hour=sc.start_hour, end_hour=sc.end_hour) for sc in body.custom_slots),
    )
    repo.save(settings)
    reschedule(body.cron_expression)
    return body
