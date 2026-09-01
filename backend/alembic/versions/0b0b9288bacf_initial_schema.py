"""Initial schema.

The initial revision intentionally delegates table creation to the canonical
SQLAlchemy metadata. PostgreSQL named ENUM objects are defined once in the
models (not duplicated per column), avoiding duplicate pg_type creation.
Future schema changes must be represented by explicit Alembic revisions.
"""
from __future__ import annotations

from alembic import op

from ultimate_rag.db.models import Base

revision = "0b0b9288bacf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
