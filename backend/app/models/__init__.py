"""
Eksport wszystkich modeli ORM.
Import tego pakietu gwarantuje, że Alembic widzi wszystkie tabele.
"""
from app.models.country import Country
from app.models.indicator import Indicator
from app.models.data_point import DataPoint

__all__ = ["Country", "Indicator", "DataPoint"]
