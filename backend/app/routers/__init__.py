from app.routers.countries import router as countries_router
from app.routers.indicators import router as indicators_router
from app.routers.compare import router as compare_router
from app.routers.ingestion import router as ingestion_router

__all__ = [
    "countries_router",
    "indicators_router",
    "compare_router",
    "ingestion_router",
]
