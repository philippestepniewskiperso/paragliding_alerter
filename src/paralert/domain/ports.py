from abc import ABC, abstractmethod
from .models import CheckResult, Settings, Summit, WindData


class WeatherPort(ABC):
    @abstractmethod
    async def fetch_wind(
        self, lat: float, lon: float, altitudes_m: tuple[int, ...]
    ) -> WindData: ...


class SummitRepository(ABC):
    @abstractmethod
    def list(self, *, enabled_only: bool = False) -> list[Summit]: ...

    @abstractmethod
    def get(self, id: int) -> Summit: ...

    @abstractmethod
    def add(self, summit: Summit) -> Summit: ...

    @abstractmethod
    def update(self, summit: Summit) -> Summit: ...

    @abstractmethod
    def delete(self, id: int) -> None: ...


class SettingsRepository(ABC):
    @abstractmethod
    def get(self) -> Settings: ...

    @abstractmethod
    def save(self, settings: Settings) -> None: ...


class CheckResultRepository(ABC):
    @abstractmethod
    def save(self, result: CheckResult) -> None: ...

    @abstractmethod
    def last_by_summit(self) -> list[CheckResult]: ...


class NotificationPort(ABC):
    @abstractmethod
    async def send_summary(
        self,
        results: list[CheckResult],
        summits: list[Summit],
        settings: "Settings",
    ) -> None: ...
