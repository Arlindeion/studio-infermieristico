"""qualificazione e promemoria call sonno

Revision ID: 9b7e2d4c6a10
Revises: 56dda7f5137f
Create Date: 2026-07-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9b7e2d4c6a10'
down_revision = '56dda7f5137f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ruolo_richiedente', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('durata_difficolta', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('obiettivo_call', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('presa_visione_offerta', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('conferma_ambito', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('consenso_whatsapp', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('promemoria_email_24h_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('promemoria_email_2h_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('promemoria_whatsapp_24h_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('promemoria_whatsapp_2h_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('utm_source', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('utm_medium', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('utm_campaign', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('utm_content', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.drop_column('utm_content')
        batch_op.drop_column('utm_campaign')
        batch_op.drop_column('utm_medium')
        batch_op.drop_column('utm_source')
        batch_op.drop_column('promemoria_whatsapp_2h_il')
        batch_op.drop_column('promemoria_whatsapp_24h_il')
        batch_op.drop_column('promemoria_email_2h_il')
        batch_op.drop_column('promemoria_email_24h_il')
        batch_op.drop_column('consenso_whatsapp')
        batch_op.drop_column('conferma_ambito')
        batch_op.drop_column('presa_visione_offerta')
        batch_op.drop_column('obiettivo_call')
        batch_op.drop_column('durata_difficolta')
        batch_op.drop_column('ruolo_richiedente')
