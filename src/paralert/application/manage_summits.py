from paralert.domain.models import Summit
from paralert.domain.ports import SummitRepository


class ManageSummitsUseCase:
    def __init__(self, repo: SummitRepository):
        self._repo = repo

    def list(self) -> list[Summit]:
        return self._repo.list()

    def get(self, id: int) -> Summit:
        return self._repo.get(id)

    def add(self, summit: Summit) -> Summit:
        return self._repo.add(summit)

    def update(self, summit: Summit) -> Summit:
        return self._repo.update(summit)

    def delete(self, id: int) -> None:
        self._repo.delete(id)

    def toggle(self, id: int) -> Summit:
        summit = self._repo.get(id)
        updated = Summit(
            id=summit.id,
            name=summit.name,
            lat=summit.lat,
            lon=summit.lon,
            altitudes_m=summit.altitudes_m,
            enabled=not summit.enabled,
        )
        return self._repo.update(updated)
