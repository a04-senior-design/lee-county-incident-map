"""Add saved_areas.address.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-05

The address as the user typed it, for the notification card; lat and lon stay the
point the alerts use. Nullable, because the areas saved before this have none.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.saved_areas ADD COLUMN address text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.saved_areas DROP COLUMN address")
