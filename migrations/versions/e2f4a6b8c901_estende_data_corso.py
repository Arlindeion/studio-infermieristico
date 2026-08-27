"""estende data corso

Revision ID: e2f4a6b8c901
Revises: d91e6b4f2a30
Create Date: 2026-08-27 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e2f4a6b8c901'
down_revision = 'd91e6b4f2a30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('iscrizione_corso', schema=None) as batch_op:
        batch_op.alter_column(
            'data_corso',
            existing_type=sa.String(length=20),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('iscrizione_corso', schema=None) as batch_op:
        batch_op.alter_column(
            'data_corso',
            existing_type=sa.String(length=255),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
