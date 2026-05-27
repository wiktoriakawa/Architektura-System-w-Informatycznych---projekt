"""
Warstwa bazy danych — silnik SQLAlchemy, sesja, klasa bazowa modeli.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Klasa bazowa dla wszystkich modeli ORM."""
    pass


def get_db():
    """Dependency injection — sesja bazy danych dla FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
