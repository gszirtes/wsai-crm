"""deal ownership and ball-in-court fields

Revision ID: f4f126ea9ff4
Revises: d3a3a0092623
Create Date: 2026-07-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4f126ea9ff4'
down_revision: Union[str, None] = 'd3a3a0092623'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deals', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('deals', sa.Column('source', sa.String(), nullable=True))
    op.add_column('deals', sa.Column('last_contact_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('deals', sa.Column('ball_in_court', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('deals', 'ball_in_court')
    op.drop_column('deals', 'last_contact_at')
    op.drop_column('deals', 'source')
    op.drop_column('deals', 'claimed_at')
