"""project deal_id

Revision ID: b7f0d824c1e9
Revises: a2c5e9f13b7d
Create Date: 2026-07-22 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f0d824c1e9'
down_revision: Union[str, None] = 'a2c5e9f13b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('deal_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_projects_deal_id', 'projects', 'deals', ['deal_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_projects_deal_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'deal_id')
