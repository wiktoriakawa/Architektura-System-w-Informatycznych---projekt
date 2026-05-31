"""Endpoint REST do ręcznego uruchamiania akwizycji danych."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.ingestion import run_ingestion
from app.ingestion.indicators_config import ALL_INDICATORS

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


class IngestionTriggerRequest(BaseModel):
    year_from: int = Field(default=2010, ge=1960, le=2030)
    year_to: int = Field(default=2024, ge=1960, le=2030)
    indicators: list[str] | None = Field(
        default=None,
        description="Lista kodów wskaźników do pobrania (domyślnie wszystkie).",
    )
    run_in_background: bool = Field(
        default=True,
        description="Jeśli True, ingestion uruchamia się asynchronicznie i endpoint odpowiada od razu.",
    )


class IngestionTriggerResponse(BaseModel):
    status: str
    indicators_processed: int | None = None
    data_points_upserted: int | None = None
    observations_received: int | None = None
    observations_dropped: int | None = None
    errors: list[str] | None = None


@router.post(
    "/trigger",
    response_model=IngestionTriggerResponse,
    summary="Uruchom akwizycję danych",
    description=(
        "Pobiera dane z Eurostat i World Bank API i zapisuje je w bazie. "
        "Domyślnie wykonywane w tle — odpowiedź zwracana natychmiast."
    ),
)
def trigger_ingestion(
    request: IngestionTriggerRequest,
    background_tasks: BackgroundTasks,
) -> IngestionTriggerResponse:
    if request.year_from > request.year_to:
        raise HTTPException(status_code=400, detail="year_from must be <= year_to")

    if request.indicators:
        valid_codes = {i.code for i in ALL_INDICATORS}
        unknown = [c for c in request.indicators if c not in valid_codes]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown indicator codes: {unknown}",
            )

    if request.run_in_background:
        background_tasks.add_task(
            run_ingestion,
            request.year_from,
            request.year_to,
            request.indicators,
        )
        return IngestionTriggerResponse(status="scheduled")

    stats = run_ingestion(
        request.year_from,
        request.year_to,
        request.indicators,
    )
    return IngestionTriggerResponse(
        status="completed",
        indicators_processed=stats.indicators_processed,
        data_points_upserted=stats.data_points_upserted,
        observations_received=stats.observations_received,
        observations_dropped=stats.observations_dropped,
        errors=stats.errors,
    )
