"""strumenti operativi area admin

Revision ID: a13d8f7c2b40
Revises: 4d8b2c7a91e6
Create Date: 2026-08-13 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a13d8f7c2b40'
down_revision = '4d8b2c7a91e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('appuntamento') as batch_op:
        batch_op.add_column(sa.Column('scadenza_gestione', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sincronizzazione', sa.String(30), nullable=False, server_default='da_sincronizzare'))
        batch_op.add_column(sa.Column('difformita_calendario', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('creato_da_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('archiviato_il', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_appuntamento_scadenza_gestione', ['scadenza_gestione'])
        batch_op.create_index('ix_appuntamento_sincronizzazione', ['sincronizzazione'])
        batch_op.create_index('ix_appuntamento_archiviato_il', ['archiviato_il'])

    with op.batch_alter_table('call_sonno') as batch_op:
        batch_op.add_column(sa.Column('scadenza_gestione', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sincronizzazione', sa.String(30), nullable=False, server_default='da_sincronizzare'))
        batch_op.add_column(sa.Column('difformita_calendario', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('archiviata_il', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_call_sonno_scadenza_gestione', ['scadenza_gestione'])
        batch_op.create_index('ix_call_sonno_sincronizzazione', ['sincronizzazione'])
        batch_op.create_index('ix_call_sonno_archiviata_il', ['archiviata_il'])

    with op.batch_alter_table('corso') as batch_op:
        batch_op.add_column(sa.Column('sincronizzazione', sa.String(30), nullable=False, server_default='da_sincronizzare'))
        batch_op.add_column(sa.Column('archiviato_il', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_corso_sincronizzazione', ['sincronizzazione'])
        batch_op.create_index('ix_corso_archiviato_il', ['archiviato_il'])

    with op.batch_alter_table('incontro_accompagnamento') as batch_op:
        batch_op.add_column(sa.Column('google_event_id', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('sincronizzazione', sa.String(30), nullable=False, server_default='da_sincronizzare'))
        batch_op.add_column(sa.Column('archiviato_il', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_incontro_accompagnamento_sincronizzazione', ['sincronizzazione'])
        batch_op.create_index('ix_incontro_accompagnamento_archiviato_il', ['archiviato_il'])

    with op.batch_alter_table('iscrizione_corso') as batch_op:
        batch_op.add_column(sa.Column('scadenza_gestione', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('posti_richiesti', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('token_lista_attesa', sa.String(96), nullable=True))
        batch_op.add_column(sa.Column('invito_lista_attesa_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('scadenza_invito_lista_attesa', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('superamento_capienza_motivo', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('archiviata_il', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_iscrizione_corso_scadenza_gestione', ['scadenza_gestione'])
        batch_op.create_index('ix_iscrizione_corso_token_lista_attesa', ['token_lista_attesa'], unique=True)
        batch_op.create_index('ix_iscrizione_corso_scadenza_invito_lista_attesa', ['scadenza_invito_lista_attesa'])
        batch_op.create_index('ix_iscrizione_corso_archiviata_il', ['archiviata_il'])

    with op.batch_alter_table('registro_evento') as batch_op:
        batch_op.add_column(sa.Column('risolto_il', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('nota_risoluzione', sa.Text(), nullable=True))
        batch_op.create_index('ix_registro_evento_risolto_il', ['risolto_il'])

    op.create_table(
        'attivita_admin',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('titolo', sa.String(180), nullable=False),
        sa.Column('stato', sa.String(20), nullable=False, server_default='Aperta'),
        sa.Column('scadenza', sa.DateTime(), nullable=False),
        sa.Column('entita_tipo', sa.String(40), nullable=True),
        sa.Column('entita_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('creata_il', sa.DateTime(), nullable=False),
        sa.Column('aggiornata_il', sa.DateTime(), nullable=False),
    )
    for name, columns in [
        ('ix_attivita_admin_stato', ['stato']), ('ix_attivita_admin_scadenza', ['scadenza']),
        ('ix_attivita_admin_entita_tipo', ['entita_tipo']), ('ix_attivita_admin_entita_id', ['entita_id']),
    ]:
        op.create_index(name, 'attivita_admin', columns)

    op.create_table(
        'nota_admin',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entita_tipo', sa.String(40), nullable=False),
        sa.Column('entita_id', sa.Integer(), nullable=False),
        sa.Column('testo', sa.Text(), nullable=False),
        sa.Column('creata_il', sa.DateTime(), nullable=False),
        sa.Column('aggiornata_il', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_nota_admin_entita_tipo', 'nota_admin', ['entita_tipo'])
    op.create_index('ix_nota_admin_entita_id', 'nota_admin', ['entita_id'])
    op.create_index('ix_nota_admin_creata_il', 'nota_admin', ['creata_il'])

    op.create_table(
        'email_operativa',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entita_tipo', sa.String(40), nullable=True),
        sa.Column('entita_id', sa.Integer(), nullable=True),
        sa.Column('destinatario', sa.String(255), nullable=False),
        sa.Column('oggetto', sa.String(255), nullable=False),
        sa.Column('corpo', sa.Text(), nullable=False),
        sa.Column('stato', sa.String(20), nullable=False),
        sa.Column('errore', sa.Text(), nullable=True),
        sa.Column('inviata_il', sa.DateTime(), nullable=True),
        sa.Column('creata_il', sa.DateTime(), nullable=False),
        sa.Column('scade_il', sa.DateTime(), nullable=False),
    )
    for name, columns in [
        ('ix_email_operativa_entita_tipo', ['entita_tipo']), ('ix_email_operativa_entita_id', ['entita_id']),
        ('ix_email_operativa_stato', ['stato']), ('ix_email_operativa_inviata_il', ['inviata_il']),
        ('ix_email_operativa_scade_il', ['scade_il']),
    ]:
        op.create_index(name, 'email_operativa', columns)

    op.create_table(
        'proposta_slot',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token', sa.String(96), nullable=False),
        sa.Column('entita_tipo', sa.String(40), nullable=False),
        sa.Column('entita_id', sa.Integer(), nullable=False),
        sa.Column('data_proposta', sa.String(20), nullable=False),
        sa.Column('ora_proposta', sa.String(10), nullable=False),
        sa.Column('durata_minuti', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('stato', sa.String(20), nullable=False, server_default='Inviata'),
        sa.Column('scade_il', sa.DateTime(), nullable=False),
        sa.Column('creata_il', sa.DateTime(), nullable=False),
        sa.Column('accettata_il', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_proposta_slot_token', 'proposta_slot', ['token'], unique=True)
    op.create_index('ix_proposta_slot_entita_tipo', 'proposta_slot', ['entita_tipo'])
    op.create_index('ix_proposta_slot_entita_id', 'proposta_slot', ['entita_id'])
    op.create_index('ix_proposta_slot_stato', 'proposta_slot', ['stato'])
    op.create_index('ix_proposta_slot_scade_il', 'proposta_slot', ['scade_il'])

    op.create_table(
        'blocco_agenda',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('titolo', sa.String(160), nullable=False),
        sa.Column('data', sa.String(20), nullable=False),
        sa.Column('ora', sa.String(10), nullable=False),
        sa.Column('durata_minuti', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('google_event_id', sa.String(255), nullable=True),
        sa.Column('sincronizzazione', sa.String(30), nullable=False, server_default='da_sincronizzare'),
        sa.Column('creato_il', sa.DateTime(), nullable=False),
        sa.Column('archiviato_il', sa.DateTime(), nullable=True),
    )
    for name, columns in [
        ('ix_blocco_agenda_data', ['data']), ('ix_blocco_agenda_sincronizzazione', ['sincronizzazione']),
        ('ix_blocco_agenda_creato_il', ['creato_il']), ('ix_blocco_agenda_archiviato_il', ['archiviato_il']),
    ]:
        op.create_index(name, 'blocco_agenda', columns)

    op.create_table(
        'registro_modifica',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('azione', sa.String(80), nullable=False),
        sa.Column('entita_tipo', sa.String(40), nullable=False),
        sa.Column('entita_id', sa.Integer(), nullable=False),
        sa.Column('dettagli', sa.Text(), nullable=True),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('admin.id'), nullable=True),
        sa.Column('creato_il', sa.DateTime(), nullable=False),
    )
    for name, columns in [
        ('ix_registro_modifica_azione', ['azione']), ('ix_registro_modifica_entita_tipo', ['entita_tipo']),
        ('ix_registro_modifica_entita_id', ['entita_id']), ('ix_registro_modifica_creato_il', ['creato_il']),
    ]:
        op.create_index(name, 'registro_modifica', columns)

    op.create_table(
        'collegamento_persona',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('persona_id', sa.Integer(), sa.ForeignKey('persona_corso.id'), nullable=False),
        sa.Column('entita_tipo', sa.String(40), nullable=False),
        sa.Column('entita_id', sa.Integer(), nullable=False),
        sa.Column('creato_il', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('entita_tipo', 'entita_id', name='uq_collegamento_persona_pratica'),
    )
    op.create_index('ix_collegamento_persona_persona_id', 'collegamento_persona', ['persona_id'])
    op.create_index('ix_collegamento_persona_entita_tipo', 'collegamento_persona', ['entita_tipo'])
    op.create_index('ix_collegamento_persona_entita_id', 'collegamento_persona', ['entita_id'])


def downgrade():
    op.drop_table('collegamento_persona')
    for table in ['registro_modifica', 'blocco_agenda', 'proposta_slot', 'email_operativa', 'nota_admin', 'attivita_admin']:
        op.drop_table(table)
    with op.batch_alter_table('registro_evento') as batch_op:
        batch_op.drop_index('ix_registro_evento_risolto_il')
        batch_op.drop_column('nota_risoluzione')
        batch_op.drop_column('risolto_il')
    with op.batch_alter_table('iscrizione_corso') as batch_op:
        for index in ['ix_iscrizione_corso_archiviata_il', 'ix_iscrizione_corso_scadenza_invito_lista_attesa', 'ix_iscrizione_corso_token_lista_attesa', 'ix_iscrizione_corso_scadenza_gestione']:
            batch_op.drop_index(index)
        for column in ['archiviata_il', 'superamento_capienza_motivo', 'scadenza_invito_lista_attesa', 'invito_lista_attesa_il', 'token_lista_attesa', 'posti_richiesti', 'scadenza_gestione']:
            batch_op.drop_column(column)
    with op.batch_alter_table('incontro_accompagnamento') as batch_op:
        batch_op.drop_index('ix_incontro_accompagnamento_archiviato_il')
        batch_op.drop_index('ix_incontro_accompagnamento_sincronizzazione')
        batch_op.drop_column('archiviato_il')
        batch_op.drop_column('sincronizzazione')
        batch_op.drop_column('google_event_id')
    with op.batch_alter_table('corso') as batch_op:
        batch_op.drop_index('ix_corso_archiviato_il')
        batch_op.drop_index('ix_corso_sincronizzazione')
        batch_op.drop_column('archiviato_il')
        batch_op.drop_column('sincronizzazione')
    with op.batch_alter_table('call_sonno') as batch_op:
        for index in ['ix_call_sonno_archiviata_il', 'ix_call_sonno_sincronizzazione', 'ix_call_sonno_scadenza_gestione']:
            batch_op.drop_index(index)
        for column in ['archiviata_il', 'difformita_calendario', 'sincronizzazione', 'scadenza_gestione']:
            batch_op.drop_column(column)
    with op.batch_alter_table('appuntamento') as batch_op:
        for index in ['ix_appuntamento_archiviato_il', 'ix_appuntamento_sincronizzazione', 'ix_appuntamento_scadenza_gestione']:
            batch_op.drop_index(index)
        for column in ['archiviato_il', 'creato_da_admin', 'difformita_calendario', 'sincronizzazione', 'scadenza_gestione']:
            batch_op.drop_column(column)
