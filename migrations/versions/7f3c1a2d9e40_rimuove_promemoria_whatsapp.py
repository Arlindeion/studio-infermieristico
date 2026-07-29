"""rimuove promemoria whatsapp

Revision ID: 7f3c1a2d9e40
Revises: 9b7e2d4c6a10
Create Date: 2026-07-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7f3c1a2d9e40'
down_revision = '9b7e2d4c6a10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.drop_column('promemoria_whatsapp_2h_il')
        batch_op.drop_column('promemoria_whatsapp_24h_il')
        batch_op.drop_column('consenso_whatsapp')


def downgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.add_column(sa.Column('consenso_whatsapp', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('promemoria_whatsapp_24h_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('promemoria_whatsapp_2h_il', sa.DateTime(), nullable=True))
