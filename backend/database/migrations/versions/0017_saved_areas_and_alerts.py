"""Create saved_areas and alert_state.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-15

A saved area is a point and a radius in miles, stored as sent so it reads back
exactly; the alert query converts it to meters, the unit of geom's projection.
categories empty means every category. geom is generated from lat and lon, as on
incidents.

alert_state is the last incident a user has seen, as (geocoded_at, source,
source_incident_id). Not geocoded_at alone: a geocoding batch stamps every row with
the same time, so a bare timestamp would skip the rest of a batch. geocoded_at is
when an incident became mappable and is never rewritten once set.

The alert query also ignores incidents older than 30 days. Old incidents are still
being mapped, and without that limit each would alert as if it were new.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.saved_areas (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id        bigint      NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
            name           text        NOT NULL,
            lat            double precision NOT NULL,
            lon            double precision NOT NULL,
            geom           geometry(Point, 26959) GENERATED ALWAYS AS (
                               ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 26959)
                           ) STORED,
            radius_mi      double precision NOT NULL,
            categories     text[]      NOT NULL DEFAULT '{}',
            alerts_enabled boolean     NOT NULL DEFAULT true,
            created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX saved_areas_user_id_idx ON public.saved_areas (user_id)")

    op.execute(
        """
        CREATE TABLE public.alert_state (
            user_id            bigint      PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
            geocoded_at        timestamptz NOT NULL,
            source             text        NOT NULL,
            source_incident_id text        NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.alert_state")
    op.execute("DROP TABLE IF EXISTS public.saved_areas")
