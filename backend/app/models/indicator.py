"""
Model Indicator — wskaźniki ekonomiczne/demograficzne (PKB, bezrobocie, inflacja…).
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Indicator(Base):
    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # np. gdp_per_capita_wb
    name = Column(String(200), nullable=False)                           # np. GDP per capita (World Bank)
    unit = Column(String(100))                                           # np. current USD
    source = Column(String(50))                                          # eurostat | worldbank

    data_points = relationship("DataPoint", back_populates="indicator", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Indicator {self.code} [{self.source}]>"
