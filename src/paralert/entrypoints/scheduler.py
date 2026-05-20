import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from paralert.adapters.notification.ntfy import NtfyNotifier
from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
)
from paralert.adapters.weather.open_meteo import OpenMeteoWeather
from paralert.application.check_conditions import CheckConditionsUseCase

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_db_path: str = ""
JOB_ID = "daily_check"


def _make_use_case() -> CheckConditionsUseCase:
    settings_repo = SqliteSettingsRepository(_db_path)
    return CheckConditionsUseCase(
        weather=OpenMeteoWeather(),
        summits=SqliteSummitRepository(_db_path),
        settings=settings_repo,
        results=SqliteCheckResultRepository(_db_path),
        notifier=NtfyNotifier(settings_fn=settings_repo.get),
    )


def _run_check() -> None:
    logger.info("Running scheduled check")
    asyncio.run(_make_use_case().execute())


def start_scheduler(db_path: str) -> BackgroundScheduler:
    global _scheduler, _db_path
    _db_path = db_path

    settings = SqliteSettingsRepository(db_path).get()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_run_check, CronTrigger.from_crontab(settings.cron_expression), id=JOB_ID)
    return _scheduler


def reschedule(cron_expression: str) -> None:
    if _scheduler is None:
        return
    _scheduler.reschedule_job(JOB_ID, trigger=CronTrigger.from_crontab(cron_expression))
    logger.info("Scheduler rescheduled: %s", cron_expression)
