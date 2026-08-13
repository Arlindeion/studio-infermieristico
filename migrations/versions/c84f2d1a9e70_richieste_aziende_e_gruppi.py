"""richieste dedicate ad aziende e gruppi

Revision ID: c84f2d1a9e70
Revises: a13d8f7c2b40
Create Date: 2026-08-13 22:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c84f2d1a9e70'
down_revision = 'a13d8f7c2b40'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'richiesta_azienda',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organizzazione', sa.String(160), nullable=False),
        sa.Column('referente', sa.String(100), nullable=False),
        sa.Column('telefono', sa.String(20), nullable=False),
        sa.Column('email', sa.String(100), nullable=False),
        sa.Column('tipo_organizzazione', sa.String(60), nullable=False),
        sa.Column('corso_tipo', sa.String(80), nullable=False),
        sa.Column('partecipanti_stimati', sa.Integer(), nullable=True),
        sa.Column('sede_preferita', sa.String(60), nullable=False),
        sa.Column('periodo_preferito', sa.String(160), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('consenso_privacy', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('stato', sa.String(30), nullable=False, server_default='Nuova'),
        sa.Column('scadenza_gestione', sa.DateTime(), nullable=True),
        sa.Column('corso_generato_id', sa.Integer(), sa.ForeignKey('corso.id'), nullable=True),
        sa.Column('creato_il', sa.DateTime(), nullable=False),
        sa.Column('aggiornato_il', sa.DateTime(), nullable=False),
        sa.Column('archiviata_il', sa.DateTime(), nullable=True),
    )
    for name, columns in [
        ('ix_richiesta_azienda_organizzazione', ['organizzazione']),
        ('ix_richiesta_azienda_referente', ['referente']),
        ('ix_richiesta_azienda_email', ['email']),
        ('ix_richiesta_azienda_corso_tipo', ['corso_tipo']),
        ('ix_richiesta_azienda_stato', ['stato']),
        ('ix_richiesta_azienda_scadenza_gestione', ['scadenza_gestione']),
        ('ix_richiesta_azienda_corso_generato_id', ['corso_generato_id']),
        ('ix_richiesta_azienda_creato_il', ['creato_il']),
        ('ix_richiesta_azienda_archiviata_il', ['archiviata_il']),
    ]:
        op.create_index(name, 'richiesta_azienda', columns)


def downgrade():
    op.drop_table('richiesta_azienda')
