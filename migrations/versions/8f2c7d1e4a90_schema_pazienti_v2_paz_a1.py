"""Schema additivo Patients 2.0 - PAZ-A1 candidate.

Revision ID: 8f2c7d1e4a90
Revises: c9e1f4a7b260
Create Date: 2026-09-03

This revision is intentionally additive. It must be re-parented or regenerated
if the Alembic head changes before the patch is applied.
"""

from alembic import op
import sqlalchemy as sa


revision = '8f2c7d1e4a90'
down_revision = 'c9e1f4a7b260'
branch_labels = None
depends_on = None


def _add_person_reference(table_name, column_name, constraint_name, index_name):
    """Add a nullable patient FK without rebuilding populated SQLite tables."""
    if op.get_bind().dialect.name == 'sqlite':
        # SQLite supports a nullable REFERENCES column through ALTER TABLE.
        # Alembic batch mode would rebuild the parent table and break existing
        # child references while foreign-key enforcement is enabled.
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" '
                f'INTEGER CONSTRAINT "{constraint_name}" '
                'REFERENCES persona (id) ON DELETE RESTRICT'
            )
        )
    else:
        op.add_column(table_name, sa.Column(column_name, sa.Integer(), nullable=True))
        op.create_foreign_key(
            constraint_name,
            table_name,
            'persona',
            [column_name],
            ['id'],
            ondelete='RESTRICT',
        )
    op.create_index(index_name, table_name, [column_name], unique=False)


def _drop_person_reference(table_name, column_name, constraint_name, index_name):
    """Remove an A1 patient FK without rebuilding populated SQLite tables."""
    op.drop_index(index_name, table_name=table_name)
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint(constraint_name, table_name, type_='foreignkey')
    op.drop_column(table_name, column_name)


def upgrade():
    op.create_table(
        'persona',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(length=100), nullable=True),
        sa.Column('cognome', sa.String(length=100), nullable=True),
        sa.Column('data_nascita', sa.Date(), nullable=True),
        sa.Column('sesso_anagrafico', sa.String(length=1), nullable=True),
        sa.Column('codice_fiscale', sa.String(length=32), nullable=True),
        sa.Column('comune_nascita', sa.String(length=120), nullable=True),
        sa.Column('provincia_nascita', sa.String(length=10), nullable=True),
        sa.Column('stato_nascita', sa.String(length=120), nullable=True),
        sa.Column('indirizzo_residenza', sa.String(length=200), nullable=True),
        sa.Column('cap_residenza', sa.String(length=12), nullable=True),
        sa.Column('comune_residenza', sa.String(length=120), nullable=True),
        sa.Column('provincia_residenza', sa.String(length=10), nullable=True),
        sa.Column('stato_residenza', sa.String(length=120), nullable=True),
        sa.Column('stato', sa.String(length=20), nullable=False, server_default='attiva'),
        sa.Column('anagrafica_da_verificare', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('legacy_persona_corso_id', sa.Integer(), nullable=True),
        sa.Column('legacy_nome_completo', sa.String(length=200), nullable=True),
        sa.Column('creato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('aggiornato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('archiviato_il', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "sesso_anagrafico IS NULL OR sesso_anagrafico IN ('F','M')",
            name='ck_persona_sesso_anagrafico',
        ),
        sa.CheckConstraint(
            "stato IN ('attiva','archiviata')",
            name='ck_persona_stato',
        ),
        sa.CheckConstraint(
            "(stato = 'archiviata' AND archiviato_il IS NOT NULL) OR "
            "(stato = 'attiva' AND archiviato_il IS NULL)",
            name='ck_persona_archiviazione_coerente',
        ),
        sa.ForeignKeyConstraint(
            ['legacy_persona_corso_id'],
            ['persona_corso.id'],
            name='fk_persona_legacy_persona_corso',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('legacy_persona_corso_id', name='uq_persona_legacy_persona_corso_id'),
    )
    op.create_index('ix_persona_codice_fiscale', 'persona', ['codice_fiscale'])
    op.create_index('ix_persona_cognome_nome', 'persona', ['cognome', 'nome'])
    op.create_index('ix_persona_data_nascita', 'persona', ['data_nascita'])
    op.create_index('ix_persona_stato', 'persona', ['stato'])

    op.create_table(
        'recapito_persona',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('persona_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('valore', sa.String(length=254), nullable=False),
        sa.Column('valore_normalizzato', sa.String(length=254), nullable=False),
        sa.Column('principale', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('etichetta', sa.String(length=80), nullable=True),
        sa.Column('creato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('archiviato_il', sa.DateTime(), nullable=True),
        sa.CheckConstraint("tipo IN ('telefono','email')", name='ck_recapito_persona_tipo'),
        sa.CheckConstraint(
            'archiviato_il IS NULL OR principale = false',
            name='ck_recapito_persona_archiviato_non_principale',
        ),
        sa.ForeignKeyConstraint(['persona_id'], ['persona.id'], name='fk_recapito_persona_persona', ondelete='RESTRICT'),
        sa.UniqueConstraint('persona_id', 'tipo', 'valore_normalizzato', name='uq_recapito_persona_valore'),
    )
    op.create_index('ix_recapito_persona_persona_id', 'recapito_persona', ['persona_id'])
    op.create_index('ix_recapito_persona_ricerca', 'recapito_persona', ['tipo', 'valore_normalizzato'])
    op.create_index(
        'uq_recapito_persona_principale_attivo',
        'recapito_persona',
        ['persona_id', 'tipo'],
        unique=True,
        sqlite_where=sa.text('principale = 1 AND archiviato_il IS NULL'),
        postgresql_where=sa.text('principale IS TRUE AND archiviato_il IS NULL'),
    )

    op.create_table(
        'relazione_persona',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('persona_assistita_id', sa.Integer(), nullable=False),
        sa.Column('persona_referente_id', sa.Integer(), nullable=False),
        sa.Column('ruolo', sa.String(length=30), nullable=False),
        sa.Column('contatto_principale', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('referente_comunicazioni', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('referente_consensi', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('stato', sa.String(length=20), nullable=False, server_default='attiva'),
        sa.Column('creato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('aggiornato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('archiviato_il', sa.DateTime(), nullable=True),
        sa.CheckConstraint('persona_assistita_id <> persona_referente_id', name='ck_relazione_persona_no_self'),
        sa.CheckConstraint(
            "ruolo IN ('madre','padre','tutore','affidatario','caregiver','altro')",
            name='ck_relazione_persona_ruolo',
        ),
        sa.CheckConstraint("stato IN ('attiva','archiviata')", name='ck_relazione_persona_stato'),
        sa.CheckConstraint(
            "(stato = 'attiva' AND archiviato_il IS NULL) OR "
            "(stato = 'archiviata' AND archiviato_il IS NOT NULL)",
            name='ck_relazione_persona_archiviazione_coerente',
        ),
        sa.CheckConstraint(
            "archiviato_il IS NULL OR "
            "(contatto_principale = false AND referente_comunicazioni = false AND referente_consensi = false)",
            name='ck_relazione_persona_archiviata_senza_ruoli_attivi',
        ),
        sa.ForeignKeyConstraint(['persona_assistita_id'], ['persona.id'], name='fk_relazione_persona_assistita', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['persona_referente_id'], ['persona.id'], name='fk_relazione_persona_referente', ondelete='RESTRICT'),
        sa.UniqueConstraint('persona_assistita_id', 'persona_referente_id', 'ruolo', name='uq_relazione_persona'),
    )
    op.create_index('ix_relazione_persona_assistita_id', 'relazione_persona', ['persona_assistita_id'])
    op.create_index('ix_relazione_persona_referente_id', 'relazione_persona', ['persona_referente_id'])
    op.create_index(
        'uq_relazione_persona_contatto_principale_attivo',
        'relazione_persona',
        ['persona_assistita_id'],
        unique=True,
        sqlite_where=sa.text("contatto_principale = 1 AND stato = 'attiva' AND archiviato_il IS NULL"),
        postgresql_where=sa.text("contatto_principale IS TRUE AND stato = 'attiva' AND archiviato_il IS NULL"),
    )
    op.create_index(
        'uq_relazione_persona_comunicazioni_attivo',
        'relazione_persona',
        ['persona_assistita_id'],
        unique=True,
        sqlite_where=sa.text("referente_comunicazioni = 1 AND stato = 'attiva' AND archiviato_il IS NULL"),
        postgresql_where=sa.text("referente_comunicazioni IS TRUE AND stato = 'attiva' AND archiviato_il IS NULL"),
    )

    op.create_table(
        'segnalazione_duplicato',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('persona_a_id', sa.Integer(), nullable=False),
        sa.Column('persona_b_id', sa.Integer(), nullable=False),
        sa.Column('livello', sa.String(length=20), nullable=False),
        sa.Column('creato_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint('persona_a_id < persona_b_id', name='ck_segnalazione_duplicato_id_ordinati'),
        sa.CheckConstraint("livello IN ('forte','probabile')", name='ck_segnalazione_duplicato_livello'),
        sa.ForeignKeyConstraint(['persona_a_id'], ['persona.id'], name='fk_segnalazione_duplicato_persona_a', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['persona_b_id'], ['persona.id'], name='fk_segnalazione_duplicato_persona_b', ondelete='RESTRICT'),
        sa.UniqueConstraint('persona_a_id', 'persona_b_id', name='uq_segnalazione_duplicato_coppia'),
    )
    op.create_index('ix_segnalazione_duplicato_persona_a_id', 'segnalazione_duplicato', ['persona_a_id'])
    op.create_index('ix_segnalazione_duplicato_persona_b_id', 'segnalazione_duplicato', ['persona_b_id'])

    op.create_table(
        'fusione_persona',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('persona_principale_id', sa.Integer(), nullable=False),
        sa.Column('persona_secondaria_id', sa.Integer(), nullable=False),
        sa.Column('operazione_id', sa.String(length=36), nullable=False),
        sa.Column('stato', sa.String(length=20), nullable=False, server_default='applicata'),
        sa.Column('applicata_il', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('annullata_il', sa.DateTime(), nullable=True),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.CheckConstraint('persona_principale_id <> persona_secondaria_id', name='ck_fusione_persona_no_self'),
        sa.CheckConstraint("stato IN ('applicata','annullata')", name='ck_fusione_persona_stato'),
        sa.CheckConstraint(
            "(stato = 'applicata' AND annullata_il IS NULL) OR "
            "(stato = 'annullata' AND annullata_il IS NOT NULL)",
            name='ck_fusione_persona_stato_temporale',
        ),
        sa.ForeignKeyConstraint(['persona_principale_id'], ['persona.id'], name='fk_fusione_persona_principale', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['persona_secondaria_id'], ['persona.id'], name='fk_fusione_persona_secondaria', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin.id'], name='fk_fusione_persona_admin', ondelete='RESTRICT'),
        sa.UniqueConstraint('operazione_id', name='uq_fusione_persona_operazione_id'),
    )
    op.create_index('ix_fusione_persona_principale_id', 'fusione_persona', ['persona_principale_id'])
    op.create_index('ix_fusione_persona_secondaria_id', 'fusione_persona', ['persona_secondaria_id'])

    _add_person_reference(
        'appuntamento',
        'persona_id',
        'fk_appuntamento_persona_v2',
        'ix_appuntamento_persona_id',
    )
    _add_person_reference(
        'call_sonno',
        'persona_id',
        'fk_call_sonno_persona_v2',
        'ix_call_sonno_persona_id',
    )
    _add_person_reference(
        'iscrizione_corso',
        'persona_v2_id',
        'fk_iscrizione_corso_persona_v2',
        'ix_iscrizione_corso_persona_v2_id',
    )


def downgrade():
    _drop_person_reference(
        'iscrizione_corso',
        'persona_v2_id',
        'fk_iscrizione_corso_persona_v2',
        'ix_iscrizione_corso_persona_v2_id',
    )
    _drop_person_reference(
        'call_sonno',
        'persona_id',
        'fk_call_sonno_persona_v2',
        'ix_call_sonno_persona_id',
    )
    _drop_person_reference(
        'appuntamento',
        'persona_id',
        'fk_appuntamento_persona_v2',
        'ix_appuntamento_persona_id',
    )

    op.drop_index('ix_fusione_persona_secondaria_id', table_name='fusione_persona')
    op.drop_index('ix_fusione_persona_principale_id', table_name='fusione_persona')
    op.drop_table('fusione_persona')

    op.drop_index('ix_segnalazione_duplicato_persona_b_id', table_name='segnalazione_duplicato')
    op.drop_index('ix_segnalazione_duplicato_persona_a_id', table_name='segnalazione_duplicato')
    op.drop_table('segnalazione_duplicato')

    op.drop_index('uq_relazione_persona_comunicazioni_attivo', table_name='relazione_persona')
    op.drop_index('uq_relazione_persona_contatto_principale_attivo', table_name='relazione_persona')
    op.drop_index('ix_relazione_persona_referente_id', table_name='relazione_persona')
    op.drop_index('ix_relazione_persona_assistita_id', table_name='relazione_persona')
    op.drop_table('relazione_persona')

    op.drop_index('uq_recapito_persona_principale_attivo', table_name='recapito_persona')
    op.drop_index('ix_recapito_persona_ricerca', table_name='recapito_persona')
    op.drop_index('ix_recapito_persona_persona_id', table_name='recapito_persona')
    op.drop_table('recapito_persona')

    op.drop_index('ix_persona_stato', table_name='persona')
    op.drop_index('ix_persona_data_nascita', table_name='persona')
    op.drop_index('ix_persona_cognome_nome', table_name='persona')
    op.drop_index('ix_persona_codice_fiscale', table_name='persona')
    op.drop_table('persona')
