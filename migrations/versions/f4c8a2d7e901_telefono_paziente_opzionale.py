"""rende opzionale il telefono paziente

Revision ID: f4c8a2d7e901
Revises: e2f4a6b8c901
Create Date: 2026-08-28 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f4c8a2d7e901'
down_revision = 'e2f4a6b8c901'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('persona_corso', schema=None) as batch_op:
        batch_op.alter_column(
            'telefono',
            existing_type=sa.String(length=20),
            existing_nullable=False,
            nullable=True,
        )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE persona_corso SET telefono = '' WHERE telefono IS NULL"
        )
    )
    with op.batch_alter_table('persona_corso', schema=None) as batch_op:
        batch_op.alter_column(
            'telefono',
            existing_type=sa.String(length=20),
            existing_nullable=True,
            nullable=False,
        )
