"""project follow-up fields and deal is_stale

Revision ID: d4e8a1f52c6b
Revises: b7f0d824c1e9
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8a1f52c6b'
down_revision: Union[str, None] = 'b7f0d824c1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('projects', sa.Column('follow_up_days', sa.Integer(), nullable=False, server_default='60'))
    op.add_column('projects', sa.Column('satisfaction_score', sa.Integer(), nullable=True))
    op.add_column('deals', sa.Column('is_stale', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('deals', 'is_stale')
    op.drop_column('projects', 'satisfaction_score')
    op.drop_column('projects', 'follow_up_days')
    op.drop_column('projects', 'closed_at')
