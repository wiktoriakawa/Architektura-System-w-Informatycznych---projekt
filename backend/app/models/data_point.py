"""
Model DataPoint — pojedynczy punkt danych (kraj × wskaźnik × rok → wartość).
"""
from sqlalchemy import Column, Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


class DataPoint(Base):
    __tablename__ = "data_points"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    indicator_id = Column(Integer, ForeignKey("indicators.id"), nullable=False)
    year = Column(Integer, nullable=False, index=True)
    value = Column(Float)

    country = relationship("Country", back_populates="data_points")
    indicator = relationship("Indicator", back_populates="data_points")

    __table_args__ = (
        UniqueConstraint("country_id", "indicator_id", "year", name="uq_country_indicator_year"),
        Index("ix_datapoint_lookup", "indicator_id", "country_id", "year"),
    )

    def __repr__(self) -> str:
        return f"<DataPoint country={self.country_id} indicator={self.indicator_id} year={self.year} value={self.value}>"
