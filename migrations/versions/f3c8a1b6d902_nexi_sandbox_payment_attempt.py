"""Track isolated Nexi sandbox payment attempts.

Revision ID: f3c8a1b6d902
Revises: e8b1c4d7a902
"""

from alembic import op
import sqlalchemy as sa


revision = 'f3c8a1b6d902'
down_revision = 'e8b1c4d7a902'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sandbox_payment_attempt',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.String(18), nullable=False, unique=True),
        sa.Column('access_token', sa.String(96), nullable=False, unique=True),
        sa.Column('sleep_call_id', sa.Integer(), nullable=False),
        sa.Column('active_call_id', sa.Integer(), nullable=True, unique=True),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('formula', sa.String(30), nullable=False),
        sa.Column('terms_version', sa.String(20), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=False),
        sa.Column('proposal_digest', sa.String(64), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('security_token_hash', sa.String(64), nullable=True),
        sa.Column('checkout_url', sa.Text(), nullable=True),
        sa.Column('operation_id', sa.String(120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['sleep_call_id'], ['call_sonno.id'],
            name='fk_sandbox_payment_sleep_call', ondelete='CASCADE',
        ),
    )


def downgrade():
    attempts = sa.table('sandbox_payment_attempt', sa.column('id', sa.Integer()))
    if op.get_bind().execute(sa.select(attempts.c.id).limit(1)).first() is not None:
        raise RuntimeError('Il downgrade non può eliminare tentativi di pagamento sandbox esistenti.')
    op.drop_table('sandbox_payment_attempt')
