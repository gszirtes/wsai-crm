"""milestone table

Revision ID: a2c5e9f13b7d
Revises: d1b4426e7cd8
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c5e9f13b7d'
down_revision: Union[str, None] = 'd1b4426e7cd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'milestones',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('work_status', sa.String(), nullable=False),
        sa.Column('payment_status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_milestones_project_id'), 'milestones', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_milestones_project_id'), table_name='milestones')
    op.drop_table('milestones')
