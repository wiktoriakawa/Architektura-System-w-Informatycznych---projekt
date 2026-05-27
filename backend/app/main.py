"""
TrendEconomy — główny punkt wejścia aplikacji FastAPI.
"""
import time

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import LOG_LEVEL
from app.routers import countries, indicators, compare

# ---------------------------------------------------------------------------
# Konfiguracja logowania strukturalnego
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Aplikacja FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TrendEconomy API",
    description=(
        "Analiza trendów ekonomicznych i demograficznych Polski na tle Unii Europejskiej. "
        "Dane pobierane z Eurostat API oraz World Bank API."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware — CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji: konkretne origin(y)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware — logowanie czasu odpowiedzi
# ---------------------------------------------------------------------------
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


app.add_middleware(LoggingMiddleware)

# ---------------------------------------------------------------------------
# Rejestracja routerów
# ---------------------------------------------------------------------------
app.include_router(countries.router)
app.include_router(indicators.router)
app.include_router(compare.router)


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("app_started", log_level=LOG_LEVEL)
