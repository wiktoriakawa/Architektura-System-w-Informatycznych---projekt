"""Moduł akwizycji danych z Eurostat i World Bank."""
from app.ingestion.run import IngestionStats, run_ingestion

__all__ = ["IngestionStats", "run_ingestion"]
