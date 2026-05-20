import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends

from paralert.application.check_conditions import CheckConditionsUseCase
from paralert.domain.ports import CheckResultRepository

from .deps import get_check_conditions_use_case, get_results_repo
from .schemas import CheckResultRead

router = APIRouter(prefix="/checks", tags=["checks"])


@router.post("/now", status_code=202)
def trigger_check_now(
    background_tasks: BackgroundTasks,
    uc: CheckConditionsUseCase = Depends(get_check_conditions_use_case),
):
    background_tasks.add_task(_run, uc)
    return {"started": True}


@router.get("/last", response_model=list[CheckResultRead])
def get_last_results(repo: CheckResultRepository = Depends(get_results_repo)):
    return [
        CheckResultRead(
            summit_id=r.summit_id,
            target_date=r.target_date,
            calm_hours=list(r.calm_hours),
            max_wind_kmh=r.max_wind_kmh,
            checked_at=r.checked_at,
        )
        for r in repo.last_by_summit()
    ]


async def _run(uc: CheckConditionsUseCase) -> None:
    await uc.execute()
