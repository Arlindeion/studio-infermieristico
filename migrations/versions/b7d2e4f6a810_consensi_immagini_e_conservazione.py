"""consensi immagini e conservazione privacy

Revision ID: b7d2e4f6a810
Revises: a6c9e1f4b802
Create Date: 2026-08-29 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7d2e4f6a810'
down_revision = 'a6c9e1f4b802'
branch_labels = None
depends_on = None


def upgrade():
    for table_name in [
        'appuntamento',
        'call_sonno',
        'persona_corso',
        'iscrizione_corso',
        'richiesta_azienda',
    ]:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column('dati_anonimizzati_il', sa.DateTime(), nullable=True))
            batch_op.create_index(
                batch_op.f(f'ix_{table_name}_dati_anonimizzati_il'),
                ['dati_anonimizzati_il'],
                unique=False,
            )

    with op.batch_alter_table('iscrizione_corso', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'consenso_dati_gravidanza',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))
        batch_op.add_column(sa.Column('consenso_dati_gravidanza_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('informativa_terzi_consegnata_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('informativa_terzi_destinatario', sa.String(length=160), nullable=True))

    op.create_table(
        'autorizzazione_immagini',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('iscrizione_id', sa.Integer(), nullable=False),
        sa.Column('soggetto_nome', sa.String(length=160), nullable=False),
        sa.Column('soggetto_tipo', sa.String(length=20), nullable=False),
        sa.Column('finalita_didattica', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('finalita_informativa', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('finalita_promozionale', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('canale_sito', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('canale_social', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('canale_materiali', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('primo_genitore_nome', sa.String(length=160), nullable=True),
        sa.Column('secondo_genitore_nome', sa.String(length=160), nullable=True),
        sa.Column('responsabilita_esclusiva', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('versione_informativa', sa.String(length=20), nullable=False),
        sa.Column('prestato_il', sa.DateTime(), nullable=False),
        sa.Column('revocato_il', sa.DateTime(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['iscrizione_id'], ['iscrizione_corso.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('autorizzazione_immagini', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_autorizzazione_immagini_iscrizione_id'),
            ['iscrizione_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_autorizzazione_immagini_prestato_il'),
            ['prestato_il'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_autorizzazione_immagini_revocato_il'),
            ['revocato_il'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('autorizzazione_immagini', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_autorizzazione_immagini_revocato_il'))
        batch_op.drop_index(batch_op.f('ix_autorizzazione_immagini_prestato_il'))
        batch_op.drop_index(batch_op.f('ix_autorizzazione_immagini_iscrizione_id'))
    op.drop_table('autorizzazione_immagini')

    with op.batch_alter_table('iscrizione_corso', schema=None) as batch_op:
        batch_op.drop_column('informativa_terzi_destinatario')
        batch_op.drop_column('informativa_terzi_consegnata_il')
        batch_op.drop_column('consenso_dati_gravidanza_il')
        batch_op.drop_column('consenso_dati_gravidanza')

    for table_name in [
        'richiesta_azienda',
        'iscrizione_corso',
        'persona_corso',
        'call_sonno',
        'appuntamento',
    ]:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f'ix_{table_name}_dati_anonimizzati_il'))
            batch_op.drop_column('dati_anonimizzati_il')
