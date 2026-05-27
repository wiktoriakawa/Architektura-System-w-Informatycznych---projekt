"""initial tables

Revision ID: 001_initial
Revises:
Create Date: 2025-06-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- countries ---
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_iso2", sa.String(2), nullable=False),
        sa.Column("code_iso3", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("region", sa.String(50), nullable=True),
    )
    op.create_index("ix_countries_id", "countries", ["id"])
    op.create_index("ix_countries_code_iso2", "countries", ["code_iso2"], unique=True)
    op.create_index("ix_countries_code_iso3", "countries", ["code_iso3"], unique=True)

    # --- indicators ---
    op.create_table(
        "indicators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
    )
    op.create_index("ix_indicators_id", "indicators", ["id"])
    op.create_index("ix_indicators_code", "indicators", ["code"], unique=True)

    # --- data_points ---
    op.create_table(
        "data_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("indicator_id", sa.Integer(), sa.ForeignKey("indicators.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
    )
    op.create_index("ix_data_points_id", "data_points", ["id"])
    op.create_index("ix_data_points_year", "data_points", ["year"])
    op.create_index("ix_datapoint_lookup", "data_points", ["indicator_id", "country_id", "year"])
    op.create_unique_constraint("uq_country_indicator_year", "data_points", ["country_id", "indicator_id", "year"])


def downgrade() -> None:
    op.drop_table("data_points")
    op.drop_table("indicators")
    op.drop_table("countries")
