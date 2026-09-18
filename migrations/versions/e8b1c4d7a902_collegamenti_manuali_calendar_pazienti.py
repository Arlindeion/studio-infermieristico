"""Add audited manual Calendar-to-patient decisions.

Revision ID: e8b1c4d7a902
Revises: d4a7c2e9f610
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


revision = 'e8b1c4d7a902'
down_revision = 'd4a7c2e9f610'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'calendar_patient_decision',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('persona_id', sa.Integer(), nullable=False),
        sa.Column('google_event_id', sa.String(length=255), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column(
            'decided_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "decision IN ('linked','rejected')",
            name='ck_calendar_patient_decision_value',
        ),
        sa.ForeignKeyConstraint(
            ['admin_id'],
            ['admin.id'],
            name='fk_calendar_patient_decision_admin',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['persona_id'],
            ['persona.id'],
            name='fk_calendar_patient_decision_persona',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'persona_id',
            'google_event_id',
            name='uq_calendar_patient_decision_patient_event',
        ),
    )
    op.create_index(
        'ix_calendar_patient_decision_patient_status',
        'calendar_patient_decision',
        ['persona_id', 'decision'],
        unique=False,
    )
    op.create_index(
        'uq_calendar_patient_decision_linked_event',
        'calendar_patient_decision',
        ['google_event_id'],
        unique=True,
        sqlite_where=sa.text("decision = 'linked'"),
        postgresql_where=sa.text("decision = 'linked'"),
    )


def downgrade():
    decision_count = op.get_bind().execute(
        sa.text('SELECT COUNT(*) FROM calendar_patient_decision')
    ).scalar_one()
    if decision_count:
        raise RuntimeError(
            'Downgrade bloccato: esistono decisioni Calendar-paziente da preservare.'
        )
    op.drop_index(
        'uq_calendar_patient_decision_linked_event',
        table_name='calendar_patient_decision',
    )
    op.drop_index(
        'ix_calendar_patient_decision_patient_status',
        table_name='calendar_patient_decision',
    )
    op.drop_table('calendar_patient_decision')
