"""
Seed — załadowanie listy krajów UE do bazy danych.
Uruchamiany raz po migracji: python -m app.seed
"""
import structlog
from app.database import SessionLocal
from app.models import Country

logger = structlog.get_logger()

EU_COUNTRIES = [
    ("AT", "AUT", "Austria"),
    ("BE", "BEL", "Belgium"),
    ("BG", "BGR", "Bulgaria"),
    ("CY", "CYP", "Cyprus"),
    ("CZ", "CZE", "Czechia"),
    ("DE", "DEU", "Germany"),
    ("DK", "DNK", "Denmark"),
    ("EE", "EST", "Estonia"),
    ("ES", "ESP", "Spain"),
    ("FI", "FIN", "Finland"),
    ("FR", "FRA", "France"),
    ("GR", "GRC", "Greece"),
    ("HR", "HRV", "Croatia"),
    ("HU", "HUN", "Hungary"),
    ("IE", "IRL", "Ireland"),
    ("IT", "ITA", "Italy"),
    ("LT", "LTU", "Lithuania"),
    ("LU", "LUX", "Luxembourg"),
    ("LV", "LVA", "Latvia"),
    ("MT", "MLT", "Malta"),
    ("NL", "NLD", "Netherlands"),
    ("PL", "POL", "Poland"),
    ("PT", "PRT", "Portugal"),
    ("RO", "ROU", "Romania"),
    ("SE", "SWE", "Sweden"),
    ("SI", "SVN", "Slovenia"),
    ("SK", "SVK", "Slovakia"),
]


def seed_countries() -> None:
    db = SessionLocal()
    try:
        added = 0
        for iso2, iso3, name in EU_COUNTRIES:
            exists = db.query(Country).filter(Country.code_iso2 == iso2).first()
            if not exists:
                db.add(Country(code_iso2=iso2, code_iso3=iso3, name=name, region="EU"))
                added += 1

        db.commit()
        logger.info("seed_countries_done", added=added, total=len(EU_COUNTRIES))
    except Exception as e:
        db.rollback()
        logger.error("seed_countries_failed", error=str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_countries()
