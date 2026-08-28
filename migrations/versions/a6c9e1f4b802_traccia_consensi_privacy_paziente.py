"""traccia consensi privacy paziente per pratica

Revision ID: a6c9e1f4b802
Revises: f4c8a2d7e901
Create Date: 2026-08-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a6c9e1f4b802'
down_revision = 'f4c8a2d7e901'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('appuntamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'consenso_privacy',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))

    op.create_table(
        'consenso_privacy_paziente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('persona_id', sa.Integer(), nullable=False),
        sa.Column('entita_tipo', sa.String(length=40), nullable=False),
        sa.Column('entita_id', sa.Integer(), nullable=False),
        sa.Column('accettato', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('accettato_il', sa.DateTime(), nullable=True),
        sa.Column('creato_il', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['persona_id'], ['persona_corso.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'entita_tipo',
            'entita_id',
            name='uq_consenso_privacy_pratica',
        ),
    )
    with op.batch_alter_table('consenso_privacy_paziente', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_consenso_privacy_paziente_persona_id'),
            ['persona_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_consenso_privacy_paziente_entita_tipo'),
            ['entita_tipo'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_consenso_privacy_paziente_entita_id'),
            ['entita_id'],
            unique=False,
        )

    op.execute(sa.text("""
        INSERT INTO consenso_privacy_paziente
            (persona_id, entita_tipo, entita_id, accettato, accettato_il, creato_il)
        SELECT
            persona_id,
            'IscrizioneCorso',
            id,
            consenso_privacy,
            CASE WHEN consenso_privacy THEN creato_il ELSE NULL END,
            CURRENT_TIMESTAMP
        FROM iscrizione_corso
        WHERE persona_id IS NOT NULL
    """))
    op.execute(sa.text("""
        INSERT INTO consenso_privacy_paziente
            (persona_id, entita_tipo, entita_id, accettato, accettato_il, creato_il)
        SELECT
            collegamento_persona.persona_id,
            'CallSonno',
            call_sonno.id,
            call_sonno.consenso_privacy,
            CASE WHEN call_sonno.consenso_privacy THEN call_sonno.creato_il ELSE NULL END,
            CURRENT_TIMESTAMP
        FROM collegamento_persona
        JOIN call_sonno
          ON collegamento_persona.entita_tipo = 'CallSonno'
         AND collegamento_persona.entita_id = call_sonno.id
    """))
    op.execute(sa.text("""
        INSERT INTO consenso_privacy_paziente
            (persona_id, entita_tipo, entita_id, accettato, accettato_il, creato_il)
        SELECT
            collegamento_persona.persona_id,
            'Appuntamento',
            appuntamento.id,
            appuntamento.consenso_privacy,
            NULL,
            CURRENT_TIMESTAMP
        FROM collegamento_persona
        JOIN appuntamento
          ON collegamento_persona.entita_tipo = 'Appuntamento'
         AND collegamento_persona.entita_id = appuntamento.id
    """))


def downgrade():
    with op.batch_alter_table('consenso_privacy_paziente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_consenso_privacy_paziente_entita_id'))
        batch_op.drop_index(batch_op.f('ix_consenso_privacy_paziente_entita_tipo'))
        batch_op.drop_index(batch_op.f('ix_consenso_privacy_paziente_persona_id'))
    op.drop_table('consenso_privacy_paziente')

    with op.batch_alter_table('appuntamento', schema=None) as batch_op:
        batch_op.drop_column('consenso_privacy')
