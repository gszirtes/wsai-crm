"""deal lead type and referral fields

Revision ID: d1b4426e7cd8
Revises: f4f126ea9ff4
Create Date: 2026-07-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1b4426e7cd8'
down_revision: Union[str, None] = 'f4f126ea9ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deals', sa.Column('lead_type', sa.String(), server_default='single', nullable=False))
    op.add_column('deals', sa.Column('contract_company_id', sa.String(), nullable=True))
    op.add_column('deals', sa.Column('contract_contact_id', sa.String(), nullable=True))
    op.add_column('deals', sa.Column('referred_by_contact_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_deals_contract_company_id_companies', 'deals', 'companies',
                          ['contract_company_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_deals_contract_contact_id_contacts', 'deals', 'contacts',
                          ['contract_contact_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_deals_referred_by_contact_id_contacts', 'deals', 'contacts',
                          ['referred_by_contact_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_deals_referred_by_contact_id_contacts', 'deals', type_='foreignkey')
    op.drop_constraint('fk_deals_contract_contact_id_contacts', 'deals', type_='foreignkey')
    op.drop_constraint('fk_deals_contract_company_id_companies', 'deals', type_='foreignkey')
    op.drop_column('deals', 'referred_by_contact_id')
    op.drop_column('deals', 'contract_contact_id')
    op.drop_column('deals', 'contract_company_id')
    op.drop_column('deals', 'lead_type')
