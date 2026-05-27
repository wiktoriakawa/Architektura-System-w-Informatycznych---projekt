"""
Konfiguracja aplikacji — ładowanie zmiennych środowiskowych.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://trendeconomy:secretpassword@db:5432/trendeconomy_db",
)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
