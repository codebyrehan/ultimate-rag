# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""allow null user_id on jobs (async ingestion may not have authenticated user)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4c2e1f8a9b3d"
down_revision = '2372969158e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.String(length=64), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.String(length=64), nullable=False)
