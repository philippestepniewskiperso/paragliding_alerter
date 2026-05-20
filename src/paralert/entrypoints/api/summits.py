from fastapi import APIRouter, Depends, HTTPException, status

from paralert.application.manage_summits import ManageSummitsUseCase
from paralert.domain.models import Summit

from .deps import get_manage_summits_use_case
from .schemas import SummitCreate, SummitRead, SummitUpdate

router = APIRouter(prefix="/summits", tags=["summits"])


def _to_read(s: Summit) -> SummitRead:
    return SummitRead(id=s.id, name=s.name, lat=s.lat, lon=s.lon, altitudes_m=list(s.altitudes_m), enabled=s.enabled)


@router.get("/", response_model=list[SummitRead])
def list_summits(uc: ManageSummitsUseCase = Depends(get_manage_summits_use_case)):
    return [_to_read(s) for s in uc.list()]


@router.post("/", response_model=SummitRead, status_code=status.HTTP_201_CREATED)
def add_summit(body: SummitCreate, uc: ManageSummitsUseCase = Depends(get_manage_summits_use_case)):
    summit = Summit(id=None, name=body.name, lat=body.lat, lon=body.lon, altitudes_m=tuple(body.altitudes_m), enabled=body.enabled)
    return _to_read(uc.add(summit))


@router.put("/{id}", response_model=SummitRead)
def update_summit(id: int, body: SummitUpdate, uc: ManageSummitsUseCase = Depends(get_manage_summits_use_case)):
    _assert_exists(id, uc)
    summit = Summit(id=id, name=body.name, lat=body.lat, lon=body.lon, altitudes_m=tuple(body.altitudes_m), enabled=body.enabled)
    return _to_read(uc.update(summit))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_summit(id: int, uc: ManageSummitsUseCase = Depends(get_manage_summits_use_case)):
    _assert_exists(id, uc)
    uc.delete(id)


@router.patch("/{id}/toggle", response_model=SummitRead)
def toggle_summit(id: int, uc: ManageSummitsUseCase = Depends(get_manage_summits_use_case)):
    _assert_exists(id, uc)
    return _to_read(uc.toggle(id))


def _assert_exists(id: int, uc: ManageSummitsUseCase) -> None:
    try:
        uc.get(id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Summit {id} not found")
