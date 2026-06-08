"""
Orchestrator akwizycji danych — pobiera wskaźniki z Eurostat i World Bank,
zapisuje je w bazie (upsert na (country, indicator, year)).

Uruchomienie ręczne:
    python -m app.ingestion.run
    python -m app.ingestion.run --year-from 2010 --year-to 2024
    python -m app.ingestion.run --indicators gdp_per_capita_usd,life_expectancy

Endpoint API (POST /api/v1/ingestion/trigger) wywołuje funkcję `run_ingestion`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Country, DataPoint, Indicator
from app.ingestion.eurostat_client import EurostatClient
from app.ingestion.indicators_config import (
    ALL_INDICATORS,
    EUROSTAT_INDICATORS,
    WORLDBANK_INDICATORS,
    IndicatorConfig,
)
from app.ingestion.worldbank_client import WorldBankClient
from app.processing import (
    clean_observations,
    normalize_eurostat_observations,
    normalize_worldbank_observations,
)

logger = structlog.get_logger()

DEFAULT_YEAR_FROM = 2010
DEFAULT_YEAR_TO = 2024


@dataclass
class IngestionStats:
    """Podsumowanie pojedynczego uruchomienia ingestion."""

    indicators_processed: int = 0
    data_points_upserted: int = 0
    observations_received: int = 0
    observations_dropped: int = 0
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def as_dict(self) -> dict:
        return {
            "indicators_processed": self.indicators_processed,
            "data_points_upserted": self.data_points_upserted,
            "observations_received": self.observations_received,
            "observations_dropped": self.observations_dropped,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Pomocnicze operacje na bazie
# ---------------------------------------------------------------------------

def _get_or_create_indicator(db: Session, config: IndicatorConfig) -> Indicator:
    indicator = db.query(Indicator).filter(Indicator.code == config.code).first()
    if indicator is None:
        indicator = Indicator(
            code=config.code,
            name=config.name,
            unit=config.unit,
            source=config.source,
        )
        db.add(indicator)
        db.flush()
        logger.info("indicator_created", code=config.code)
    else:
        indicator.name = config.name
        indicator.unit = config.unit
        indicator.source = config.source
    return indicator


def _load_country_lookup(db: Session) -> tuple[dict[str, int], dict[str, int]]:
    """Zwraca dwie mapy: ISO2 -> country_id oraz ISO3 -> country_id."""
    countries = db.query(Country).all()
    iso2_map = {c.code_iso2: c.id for c in countries}
    iso3_map = {c.code_iso3: c.id for c in countries}
    return iso2_map, iso3_map


def _upsert_data_points(db: Session, rows: list[dict]) -> int:
    """Upsert do data_points z deduplikacją (CardinalityViolation guard)."""
    if not rows:
        return 0

    deduped: dict[tuple[int, int, int], dict] = {}
    for row in rows:
        key = (row["country_id"], row["indicator_id"], row["year"])
        deduped[key] = row
    unique_rows = list(deduped.values())

    stmt = pg_insert(DataPoint).values(unique_rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_country_indicator_year",
        set_={"value": stmt.excluded.value},
    )
    result = db.execute(stmt)
    return result.rowcount or len(unique_rows)


# ---------------------------------------------------------------------------
# Pobieranie + przetwarzanie pojedynczego źródła
# ---------------------------------------------------------------------------

def _ingest_eurostat(
    db: Session,
    indicators: list[IndicatorConfig],
    iso2_map: dict[str, int],
    year_from: int,
    year_to: int,
    stats: IngestionStats,
) -> None:
    iso2_codes = list(iso2_map.keys())
    if not iso2_codes:
        return

    with EurostatClient() as client:
        for config in indicators:
            try:
                indicator = _get_or_create_indicator(db, config)
                raw_observations = client.fetch(config, iso2_codes, year_from, year_to)
                stats.observations_received += len(raw_observations)

                normalised, norm_report = normalize_eurostat_observations(raw_observations)
                cleaned, clean_report = clean_observations(config.code, normalised)
                stats.observations_dropped += clean_report.received - clean_report.kept
                logger.info(
                    "eurostat_processing_done",
                    indicator=config.code,
                    normalization=norm_report.as_dict(),
                    cleaning=clean_report.as_dict(),
                )

                rows = [
                    {
                        "country_id": iso2_map[obs.country_iso2],
                        "indicator_id": indicator.id,
                        "year": obs.year,
                        "value": obs.value,
                    }
                    for obs in cleaned
                    if obs.country_iso2 in iso2_map
                ]
                inserted = _upsert_data_points(db, rows)
                db.commit()
                stats.indicators_processed += 1
                stats.data_points_upserted += inserted
                logger.info(
                    "eurostat_indicator_ingested",
                    indicator=config.code,
                    rows=inserted,
                )
            except Exception as e:
                db.rollback()
                stats.errors.append(f"{config.code}: {e}")
                logger.error(
                    "eurostat_ingest_failed",
                    indicator=config.code,
                    error=str(e),
                )


def _ingest_worldbank(
    db: Session,
    indicators: list[IndicatorConfig],
    iso3_map: dict[str, int],
    year_from: int,
    year_to: int,
    stats: IngestionStats,
) -> None:
    iso3_codes = list(iso3_map.keys())
    if not iso3_codes:
        return

    with WorldBankClient() as client:
        for config in indicators:
            try:
                indicator = _get_or_create_indicator(db, config)
                raw_observations = client.fetch(config, iso3_codes, year_from, year_to)
                stats.observations_received += len(raw_observations)

                normalised, norm_report = normalize_worldbank_observations(raw_observations)
                cleaned, clean_report = clean_observations(config.code, normalised)
                stats.observations_dropped += clean_report.received - clean_report.kept
                logger.info(
                    "worldbank_processing_done",
                    indicator=config.code,
                    normalization=norm_report.as_dict(),
                    cleaning=clean_report.as_dict(),
                )

                rows = [
                    {
                        "country_id": iso3_map[obs.country_iso3],
                        "indicator_id": indicator.id,
                        "year": obs.year,
                        "value": obs.value,
                    }
                    for obs in cleaned
                    if obs.country_iso3 in iso3_map
                ]
                inserted = _upsert_data_points(db, rows)
                db.commit()
                stats.indicators_processed += 1
                stats.data_points_upserted += inserted
                logger.info(
                    "worldbank_indicator_ingested",
                    indicator=config.code,
                    rows=inserted,
                )
            except Exception as e:
                db.rollback()
                stats.errors.append(f"{config.code}: {e}")
                logger.error(
                    "worldbank_ingest_failed",
                    indicator=config.code,
                    error=str(e),
                )


# ---------------------------------------------------------------------------
# Publiczny punkt wejścia
# ---------------------------------------------------------------------------

def run_ingestion(
    year_from: int = DEFAULT_YEAR_FROM,
    year_to: int = DEFAULT_YEAR_TO,
    indicator_codes: list[str] | None = None,
) -> IngestionStats:
    """Pobiera dane dla wybranych wskaźników i zapisuje je w bazie."""
    if year_from > year_to:
        raise ValueError("year_from must be <= year_to")

    if indicator_codes:
        selected = [i for i in ALL_INDICATORS if i.code in set(indicator_codes)]
        if not selected:
            raise ValueError(f"No indicators matched: {indicator_codes}")
    else:
        selected = ALL_INDICATORS

    eurostat_selected = [i for i in selected if i.source == "eurostat"]
    worldbank_selected = [i for i in selected if i.source == "worldbank"]

    logger.info(
        "ingestion_started",
        year_from=year_from,
        year_to=year_to,
        eurostat_count=len(eurostat_selected),
        worldbank_count=len(worldbank_selected),
    )

    stats = IngestionStats()
    db = SessionLocal()
    try:
        iso2_map, iso3_map = _load_country_lookup(db)
        if not iso2_map:
            raise RuntimeError(
                "Brak krajow w bazie. Uruchom najpierw `python -m app.seed`."
            )

        _ingest_eurostat(db, eurostat_selected, iso2_map, year_from, year_to, stats)
        _ingest_worldbank(db, worldbank_selected, iso3_map, year_from, year_to, stats)
    finally:
        db.close()

    logger.info("ingestion_finished", **stats.as_dict())
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TrendEconomy data ingestion")
    parser.add_argument("--year-from", type=int, default=DEFAULT_YEAR_FROM)
    parser.add_argument("--year-to", type=int, default=DEFAULT_YEAR_TO)
    parser.add_argument(
        "--indicators",
        type=str,
        default=None,
        help="Kody wskaznikow oddzielone przecinkami (domyslnie wszystkie)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    codes = [c.strip() for c in args.indicators.split(",")] if args.indicators else None
    result = run_ingestion(args.year_from, args.year_to, codes)
    print(result.as_dict())
