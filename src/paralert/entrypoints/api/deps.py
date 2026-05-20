from functools import lru_cache

from paralert.adapters.notification.ntfy import NtfyNotifier
from paralert.adapters.storage.sqlite import (
    SqliteCheckResultRepository,
    SqliteSettingsRepository,
    SqliteSummitRepository,
)
from paralert.adapters.weather.open_meteo import OpenMeteoWeather
from paralert.application.check_conditions import CheckConditionsUseCase
from paralert.application.manage_summits import ManageSummitsUseCase
from paralert.config import get_app_config
from paralert.domain.ports import (
    CheckResultRepository,
    SettingsRepository,
    SummitRepository,
)


def get_db_path() -> str:
    return get_app_config().db_path


def get_summit_repo() -> SummitRepository:
    return SqliteSummitRepository(get_db_path())


def get_settings_repo() -> SettingsRepository:
    return SqliteSettingsRepository(get_db_path())


def get_results_repo() -> CheckResultRepository:
    return SqliteCheckResultRepository(get_db_path())


def get_manage_summits_use_case() -> ManageSummitsUseCase:
    return ManageSummitsUseCase(get_summit_repo())


def get_check_conditions_use_case() -> CheckConditionsUseCase:
    settings_repo = get_settings_repo()
    notifier = NtfyNotifier(settings_fn=settings_repo.get)
    return CheckConditionsUseCase(
        weather=OpenMeteoWeather(),
        summits=get_summit_repo(),
        settings=settings_repo,
        results=get_results_repo(),
        notifier=notifier,
    )
