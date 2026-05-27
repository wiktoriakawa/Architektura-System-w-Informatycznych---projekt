"""Endpointy REST — lista krajów."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Country
from app.schemas.country import CountryOut

router = APIRouter(prefix="/api/v1/countries", tags=["Countries"])


@router.get(
    "/",
    response_model=list[CountryOut],
    summary="Lista krajów",
    description="Zwraca wszystkie kraje dostępne w bazie danych, posortowane alfabetycznie.",
)
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.name).all()


@router.get(
    "/{code_iso2}",
    response_model=CountryOut,
    summary="Szczegóły kraju",
    description="Zwraca dane kraju po kodzie ISO2 (np. PL, DE, FR).",
)
def get_country(code_iso2: str, db: Session = Depends(get_db)):
    country = db.query(Country).filter(Country.code_iso2 == code_iso2.upper()).first()
    if not country:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Country '{code_iso2}' not found")
    return country
