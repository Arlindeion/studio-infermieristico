"""Track isolated course checkout attempts.

Revision ID: b7e2d9c4a601
Revises: f3c8a1b6d902
"""

from alembic import op
import sqlalchemy as sa


revision = 'b7e2d9c4a601'
down_revision = 'f3c8a1b6d902'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sandbox_course_payment_attempt',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.String(18), nullable=False, unique=True),
        sa.Column('access_token', sa.String(96), nullable=False, unique=True),
        sa.Column('registration_id', sa.Integer(), nullable=False),
        sa.Column('active_registration_id', sa.Integer(), nullable=True, unique=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('participation', sa.String(100), nullable=False),
        sa.Column('purchase_digest', sa.String(64), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('security_token_hash', sa.String(64), nullable=True),
        sa.Column('checkout_url', sa.Text(), nullable=True),
        sa.Column('operation_id', sa.String(120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['registration_id'], ['iscrizione_corso.id'],
                                name='fk_sandbox_course_payment_registration', ondelete='CASCADE'),
    )


def downgrade():
    attempts = sa.table('sandbox_course_payment_attempt', sa.column('id', sa.Integer()))
    if op.get_bind().execute(sa.select(attempts.c.id).limit(1)).first() is not None:
        raise RuntimeError('Il downgrade non può eliminare tentativi di pagamento corso esistenti.')
    op.drop_table('sandbox_course_payment_attempt')
