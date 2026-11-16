"""Add users.name.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-12

Nullable, because the accounts made before this have no name. Register requires one
from now on.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.users ADD COLUMN name text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.users DROP COLUMN name")
