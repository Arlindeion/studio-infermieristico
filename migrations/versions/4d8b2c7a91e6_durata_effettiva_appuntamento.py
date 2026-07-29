"""durata effettiva appuntamento

Revision ID: 4d8b2c7a91e6
Revises: 7f3c1a2d9e40
Create Date: 2026-07-29 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '4d8b2c7a91e6'
down_revision = '7f3c1a2d9e40'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('appuntamento', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'duration_minutes',
                sa.Integer(),
                nullable=False,
                server_default='30',
            )
        )


def downgrade():
    with op.batch_alter_table('appuntamento', schema=None) as batch_op:
        batch_op.drop_column('duration_minutes')
