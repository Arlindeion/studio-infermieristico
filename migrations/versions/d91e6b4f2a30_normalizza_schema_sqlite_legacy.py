"""normalizza schema SQLite legacy

Revision ID: d91e6b4f2a30
Revises: c84f2d1a9e70
Create Date: 2026-08-13 22:35:00.000000

Questa revisione riallinea soltanto database SQLite storici, creati prima
della baseline Alembic e poi adottati. Su database nati dalle migrazioni lo
schema è già corretto e non viene modificato.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd91e6b4f2a30'
down_revision = 'c84f2d1a9e70'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'call_sonno'):
        unique_names = {
            constraint.get('name')
            for constraint in inspector.get_unique_constraints('call_sonno')
        }
        if 'uq_call_sonno_data_ora' in unique_names:
            with op.batch_alter_table('call_sonno') as batch_op:
                batch_op.drop_constraint('uq_call_sonno_data_ora', type_='unique')

    inspector = sa.inspect(bind)
    if _has_table(inspector, 'corso'):
        columns = {column['name']: column for column in inspector.get_columns('corso')}
        durata = columns.get('durata_ore')
        if durata and durata.get('nullable'):
            op.execute(sa.text('UPDATE corso SET durata_ore = 2 WHERE durata_ore IS NULL'))
            with op.batch_alter_table('corso') as batch_op:
                batch_op.alter_column(
                    'durata_ore',
                    existing_type=sa.Float(),
                    nullable=False,
                )

    inspector = sa.inspect(bind)
    if _has_table(inspector, 'iscrizione_corso'):
        existing_foreign_keys = {
            tuple(foreign_key.get('constrained_columns') or [])
            for foreign_key in inspector.get_foreign_keys('iscrizione_corso')
        }
        expected = [
            ('corso_id', 'corso', 'id'),
            ('persona_id', 'persona_corso', 'id'),
            ('percorso_accompagnamento_id', 'percorso_accompagnamento', 'id'),
        ]
        missing = [item for item in expected if (item[0],) not in existing_foreign_keys]
        if missing:
            with op.batch_alter_table('iscrizione_corso') as batch_op:
                for column, target_table, target_column in missing:
                    batch_op.create_foreign_key(
                        f'fk_iscrizione_corso_{column}_{target_table}',
                        target_table,
                        [column],
                        [target_column],
                    )


def downgrade():
    # Ripristinare le difformità legacy renderebbe scorretto anche un database
    # creato regolarmente da Alembic. Il downgrade conserva quindi lo schema
    # normalizzato e arretra soltanto il numero di revisione.
    pass
