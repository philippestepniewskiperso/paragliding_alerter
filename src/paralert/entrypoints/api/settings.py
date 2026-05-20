from fastapi import APIRouter, Depends

from paralert.domain.models import Settings
from paralert.domain.ports import SettingsRepository
from paralert.entrypoints.scheduler import reschedule

from .deps import get_settings_repo
from .schemas import AppSettingsRead, AppSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=AppSettingsRead)
def get_settings(repo: SettingsRepository = Depends(get_settings_repo)):
    s = repo.get()
    return AppSettingsRead(
        ntfy_url=s.ntfy_url,
        ntfy_topic=s.ntfy_topic,
        wind_calm_kmh=s.wind_calm_kmh,
        cron_expression=s.cron_expression,
    )


@router.put("/", response_model=AppSettingsRead)
def update_settings(body: AppSettingsUpdate, repo: SettingsRepository = Depends(get_settings_repo)):
    settings = Settings(
        ntfy_url=body.ntfy_url,
        ntfy_topic=body.ntfy_topic,
        wind_calm_kmh=body.wind_calm_kmh,
        cron_expression=body.cron_expression,
    )
    repo.save(settings)
    reschedule(body.cron_expression)
    return body
