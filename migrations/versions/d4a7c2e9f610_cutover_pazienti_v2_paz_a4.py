"""Cutover amministrativo Patients 2.0 - PAZ-A4.

Revision ID: d4a7c2e9f610
Revises: 8f2c7d1e4a90
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa


revision = 'd4a7c2e9f610'
down_revision = '8f2c7d1e4a90'
branch_labels = None
depends_on = None


def _has_a4_writes(bind):
    checks = (
        'SELECT 1 FROM consenso_privacy_paziente WHERE persona_v2_id IS NOT NULL LIMIT 1',
        # Any v2 identity makes the structural A4 downgrade unsafe.  A row
        # created by A2 from legacy data can already have been edited by A4,
        # even when no new practice FK or consent row has been written yet.
        'SELECT 1 FROM persona LIMIT 1',
        'SELECT 1 FROM appuntamento WHERE persona_id IS NOT NULL LIMIT 1',
        'SELECT 1 FROM call_sonno WHERE persona_id IS NOT NULL LIMIT 1',
        'SELECT 1 FROM iscrizione_corso WHERE persona_v2_id IS NOT NULL LIMIT 1',
    )
    return any(bind.execute(sa.text(statement)).first() for statement in checks)


def upgrade():
    op.add_column(
        'persona',
        sa.Column('dati_anonimizzati_il', sa.DateTime(), nullable=True),
    )
    op.create_index(
        'ix_persona_dati_anonimizzati_il',
        'persona',
        ['dati_anonimizzati_il'],
        unique=False,
    )

    with op.batch_alter_table('consenso_privacy_paziente') as batch_op:
        batch_op.alter_column(
            'persona_id',
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column('persona_v2_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_consenso_privacy_paziente_persona_v2',
            'persona',
            ['persona_v2_id'],
            ['id'],
            ondelete='RESTRICT',
        )
        batch_op.create_check_constraint(
            'ck_consenso_privacy_paziente_un_solo_modello',
            '(persona_id IS NOT NULL AND persona_v2_id IS NULL) OR '
            '(persona_id IS NULL AND persona_v2_id IS NOT NULL)',
        )
        batch_op.create_index(
            'ix_consenso_privacy_paziente_persona_v2_id',
            ['persona_v2_id'],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if _has_a4_writes(bind):
        raise RuntimeError(
            'Downgrade PAZ-A4 non sicuro: esistono dati creati dopo il cutover.'
        )

    with op.batch_alter_table('consenso_privacy_paziente') as batch_op:
        batch_op.drop_index('ix_consenso_privacy_paziente_persona_v2_id')
        batch_op.drop_constraint(
            'ck_consenso_privacy_paziente_un_solo_modello',
            type_='check',
        )
        batch_op.drop_constraint(
            'fk_consenso_privacy_paziente_persona_v2',
            type_='foreignkey',
        )
        batch_op.drop_column('persona_v2_id')
        batch_op.alter_column(
            'persona_id',
            existing_type=sa.Integer(),
            nullable=False,
        )

    op.drop_index('ix_persona_dati_anonimizzati_il', table_name='persona')
    op.drop_column('persona', 'dati_anonimizzati_il')
