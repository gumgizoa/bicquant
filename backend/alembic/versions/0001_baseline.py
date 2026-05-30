"""baseline: watchlist, sidecar_events, deviation_alerts

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-28

Matches the schema that the legacy in-code DDL produced (db.py /
monitor/db.py). For an existing database where these tables already
exist, stamp this revision instead of running it:

    alembic stamp 0001_baseline
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "sidecar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "deviation_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("target_code", sa.String(length=20), nullable=False),
        sa.Column("target_name", sa.String(length=100), nullable=False),
        sa.Column("current_value", sa.Numeric(), nullable=False),
        sa.Column("ma50", sa.Numeric(), nullable=False),
        sa.Column("deviation_ratio", sa.Numeric(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("deviation_alerts")
    op.drop_table("sidecar_events")
    op.drop_table("watchlist")
