"""Endpointy REST — pobieranie i porównywanie danych wskaźników."""
import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Country, Indicator, DataPoint
from app.schemas.data_point import IndicatorDataResponse, DataPointOut

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["Data"])


@router.get(
    "/data/{indicator_code}",
    response_model=IndicatorDataResponse,
    summary="Dane wskaźnika",
    description="Zwraca dane wybranego wskaźnika dla podanych krajów i zakresu lat.",
)
def get_indicator_data(
    indicator_code: str,
    countries: str = Query(
        default="PL,DE,FR",
        description="Kody ISO2 krajów oddzielone przecinkami (np. PL,DE,FR)",
    ),
    year_from: int = Query(default=2000, ge=1960, le=2030, description="Rok początkowy"),
    year_to: int = Query(default=2024, ge=1960, le=2030, description="Rok końcowy"),
    db: Session = Depends(get_db),
):
    # Walidacja zakresu lat
    if year_from > year_to:
        raise HTTPException(status_code=400, detail="year_from must be <= year_to")

    # Znajdź wskaźnik
    indicator = db.query(Indicator).filter(Indicator.code == indicator_code).first()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{indicator_code}' not found")

    # Parsuj kody krajów
    country_codes = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not country_codes:
        raise HTTPException(status_code=400, detail="At least one country code is required")

    logger.info(
        "fetching_indicator_data",
        indicator=indicator_code,
        countries=country_codes,
        year_from=year_from,
        year_to=year_to,
    )

    # Zapytanie do bazy
    rows = (
        db.query(DataPoint, Country)
        .join(Country, DataPoint.country_id == Country.id)
        .filter(
            DataPoint.indicator_id == indicator.id,
            Country.code_iso2.in_(country_codes),
            DataPoint.year >= year_from,
            DataPoint.year <= year_to,
        )
        .order_by(Country.code_iso2, DataPoint.year)
        .all()
    )

    data = [
        DataPointOut(
            country=country.code_iso2,
            country_name=country.name,
            year=dp.year,
            value=dp.value,
        )
        for dp, country in rows
    ]

    return IndicatorDataResponse(
        indicator=indicator.code,
        indicator_name=indicator.name,
        unit=indicator.unit,
        data=data,
    )


@router.get(
    "/health",
    summary="Health check",
    description="Sprawdza, czy serwer działa poprawnie.",
)
def health_check():
    return {"status": "ok"}
