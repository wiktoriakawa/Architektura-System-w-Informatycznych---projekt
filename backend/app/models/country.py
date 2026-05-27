"""
Model Country — kraje UE z kodami ISO.
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    code_iso2 = Column(String(2), unique=True, nullable=False, index=True)   # PL, DE, FR
    code_iso3 = Column(String(3), unique=True, nullable=False, index=True)   # POL, DEU, FRA
    name = Column(String(100), nullable=False)
    region = Column(String(50), default="EU")

    data_points = relationship("DataPoint", back_populates="country", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Country {self.code_iso2} — {self.name}>"
