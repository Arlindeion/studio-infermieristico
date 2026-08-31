"""Aggiunge offerta privata e pagamento della consulenza sonno.

Revision ID: c9e1f4a7b260
Revises: b7d2e4f6a810
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa


revision = 'c9e1f4a7b260'
down_revision = 'b7d2e4f6a810'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.add_column(sa.Column('proposta_tipo', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('proposta_token', sa.String(length=96), nullable=True))
        batch_op.add_column(sa.Column('proposta_scade_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('proposta_inviata_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('proposta_revocata_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('prezzo_centesimi', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('metodo_pagamento', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('stato_pagamento', sa.String(length=30), nullable=False, server_default='Non avviato'))
        batch_op.add_column(sa.Column('riferimento_pagamento', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('pagamento_confermato_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('condizioni_versione', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('condizioni_accettate_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('avvio_anticipato', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('avvio_anticipato_accettato_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fase_percorso', sa.String(length=30), nullable=False, server_default='non_avviato'))
        batch_op.add_column(sa.Column('supporto_whatsapp_attivato_il', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_call_sonno_proposta_token'), ['proposta_token'], unique=True)
        batch_op.create_index(batch_op.f('ix_call_sonno_stato_pagamento'), ['stato_pagamento'], unique=False)


def downgrade():
    with op.batch_alter_table('call_sonno', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_call_sonno_stato_pagamento'))
        batch_op.drop_index(batch_op.f('ix_call_sonno_proposta_token'))
        batch_op.drop_column('supporto_whatsapp_attivato_il')
        batch_op.drop_column('fase_percorso')
        batch_op.drop_column('avvio_anticipato_accettato_il')
        batch_op.drop_column('avvio_anticipato')
        batch_op.drop_column('condizioni_accettate_il')
        batch_op.drop_column('condizioni_versione')
        batch_op.drop_column('pagamento_confermato_il')
        batch_op.drop_column('riferimento_pagamento')
        batch_op.drop_column('stato_pagamento')
        batch_op.drop_column('metodo_pagamento')
        batch_op.drop_column('prezzo_centesimi')
        batch_op.drop_column('proposta_revocata_il')
        batch_op.drop_column('proposta_inviata_il')
        batch_op.drop_column('proposta_scade_il')
        batch_op.drop_column('proposta_token')
        batch_op.drop_column('proposta_tipo')
