"""Endpointy REST — lista wskaźników ekonomicznych/demograficznych."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Indicator
from app.schemas.indicator import IndicatorOut

router = APIRouter(prefix="/api/v1/indicators", tags=["Indicators"])


@router.get(
    "/",
    response_model=list[IndicatorOut],
    summary="Lista wskaźników",
    description="Zwraca wszystkie wskaźniki dostępne w systemie (PKB, bezrobocie, inflacja…).",
)
def list_indicators(db: Session = Depends(get_db)):
    return db.query(Indicator).order_by(Indicator.name).all()
