"""Delete the CommunityCrimeMap import and everything derived from it.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-10

We never got permission to use the data, so it comes out. This removes the rows and
the mapping rows the import created, and reverses migration 0012.

Order matters. The nature_categories delete reads incidents to decide which mappings
exist only to serve CCM rows, so it has to run before the rows are gone.

nature_categories is not emptied by category. The import inserted with ON CONFLICT
DO NOTHING, so a nature the Sheriff already used kept the Sheriff's meaning, and those
rows stay. What goes is the mappings no surviving incident uses.

SEX_OFFENSE stays. INDECENT EXPOSURE is a Sheriff nature and migration 0011 moved it
there on the merits, not because CCM said so. NON_CRIMINAL had no Sheriff nature at
all, so it is dropped once nothing points at it.

Migration 0013 keeps its column. The tiers it distrusts are our geocoder's, and the
error rates that justified them were measured once and are not being recomputed.

dataset_revision is bumped by hand. 0009 only put triggers on insert and update,
because at the time nothing ever deleted an incident. This is the first thing that
does, so without the bump the revision would not move and every client holding an
ETag would keep serving the rows we just deleted.

There is no downgrade. 158,131 incident rows cannot be restored, and the aliases and
the category are deliberately not put back.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE = "community_crime_map"

# Mappings that only ever described a CCM row. Anything a lee_county or traffic row
# still uses is left alone, including the ones both sources share.
ORPHANED_NATURES = text("""
    DELETE FROM public.nature_categories nc
     WHERE EXISTS (SELECT 1 FROM public.incidents i
                    WHERE i.nature = nc.nature AND i.source = :source)
       AND NOT EXISTS (SELECT 1 FROM public.incidents i
                        WHERE i.nature = nc.nature AND i.source <> :source)
""")

# The spellings migration 0012 added. CCM's address parser is the only thing that
# produces them, so nothing else reads them once the rows are gone.
CCM_ALIASES = [
    "E FORT MYERS", "S FORT MYERS", "MYERS", "FL FORT MYERS", "FL FT FORT MYERS",
    "33901 FORT MYERS", "MYER", "MYERS BEAC", "CORAL", "ACRES", "VILLAGIO ESTERO",
    "B ALVA", "FLORIDA", "FL", "FLORIDA FT", "FLORIDA FT N", "FL FT", "FL AVE",
]


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")

    bind = op.get_bind()
    bind.execute(ORPHANED_NATURES, {"source": SOURCE})
    bind.execute(
        text("DELETE FROM public.incidents WHERE source = :source"), {"source": SOURCE}
    )
    bind.execute(
        text("DELETE FROM public.city_aliases WHERE raw_city = ANY(:raws)"),
        {"raws": CCM_ALIASES},
    )

    # Guarded, so it survives anyone having mapped a real nature here in the meantime.
    op.execute(
        """
        DELETE FROM public.incident_categories c
         WHERE c.code = 'NON_CRIMINAL'
           AND NOT EXISTS (SELECT 1 FROM public.nature_categories nc
                            WHERE nc.category_code = c.code)
        """
    )

    op.execute(
        """
        UPDATE public.dataset_revision
           SET revision   = revision + 1,
               changed_at = now(),
               reason     = 'community_crime_map removed'
        """
    )


def downgrade() -> None:
    # Nothing to undo. The rows are gone and are not coming back.
    pass
