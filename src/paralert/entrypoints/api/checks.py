from fastapi import APIRouter, BackgroundTasks, Depends

from paralert.application.check_conditions import CheckConditionsUseCase
from paralert.domain.ports import CheckResultRepository

from .deps import get_check_conditions_use_case, get_results_repo
from .schemas import CalmSlotRead, CheckResultRead, WindSlotRead

router = APIRouter(prefix="/checks", tags=["checks"])


@router.post("/now", status_code=202)
def trigger_check_now(
    background_tasks: BackgroundTasks,
    uc: CheckConditionsUseCase = Depends(get_check_conditions_use_case),
):
    background_tasks.add_task(_run, uc)
    return {"started": True}


def _slot_to_read(s) -> CalmSlotRead:
    return CalmSlotRead(
        start_hour=s.start_hour,
        end_hour=s.end_hour,
        is_calm=s.is_calm,
        calm_ceiling_m=s.calm_ceiling_m,
        wind_by_altitude=[
            WindSlotRead(
                altitude_m=w.altitude_m,
                mean_speed_kmh=w.mean_speed_kmh,
                max_speed_kmh=w.max_speed_kmh,
                mean_direction_deg=w.mean_direction_deg,
            )
            for w in s.wind_by_altitude
        ],
    )


@router.get("/last", response_model=list[CheckResultRead])
def get_last_results(repo: CheckResultRepository = Depends(get_results_repo)):
    return [
        CheckResultRead(
            summit_id=r.summit_id,
            target_date=r.target_date,
            calm_slots=[_slot_to_read(s) for s in r.calm_slots],
            all_slots=[_slot_to_read(s) for s in r.all_slots],
            max_wind_kmh=r.max_wind_kmh,
            checked_at=r.checked_at,
            source=r.source,
        )
        for r in repo.last_by_summit()
    ]


async def _run(uc: CheckConditionsUseCase) -> None:
    import logging
    try:
        await uc.execute()
    except Exception:
        logging.getLogger(__name__).exception("check_conditions background task failed")
