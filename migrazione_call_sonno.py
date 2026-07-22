"""Migrazione una tantum per SQLite: call sonno e questionario riservato.

Uso, dopo un backup del database reale:
    python3 migrazione_call_sonno.py

Per PostgreSQL generare e revisionare una migrazione Flask-Migrate/Alembic.
"""
import os
import sqlite3


PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


CALL_SONNO_CORE_COLUMNS = {
    'id', 'nome', 'telefono', 'email', 'eta_bambino_mesi',
    'difficolta_principale', 'data', 'ora',
}

CALL_SONNO_ADDITIVE_COLUMNS = {
    'difficolta_altro': 'VARCHAR(300)',
    'consenso_privacy': 'BOOLEAN DEFAULT 0 NOT NULL',
    'stato': "VARCHAR(20) DEFAULT 'In attesa' NOT NULL",
    'google_event_id': 'VARCHAR(255)',
    'formula_scelta': 'VARCHAR(30)',
    'token_questionario': 'VARCHAR(96)',
    'questionario_inviato_il': 'DATETIME',
    'creato_il': 'DATETIME',
    'aggiornato_il': 'DATETIME',
}

QUESTIONARIO_SONNO_CORE_COLUMNS = {'id', 'call_sonno_id', 'risposte'}

QUESTIONARIO_SONNO_ADDITIVE_COLUMNS = {
    'consenso_dati_sanitari': 'BOOLEAN DEFAULT 0 NOT NULL',
    'consenso_marketing': 'BOOLEAN DEFAULT 0 NOT NULL',
    'compilato_il': 'DATETIME',
}


def _table_columns(conn, table_name):
    return {
        row[1]
        for row in conn.execute(f'PRAGMA table_info("{table_name}")')
    }


def _add_missing_columns(conn, table_name, columns):
    existing_columns = _table_columns(conn, table_name)
    for column_name, definition in columns.items():
        if column_name not in existing_columns:
            conn.execute(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}'
            )


def _require_core_columns(conn, table_name, required_columns):
    missing_columns = required_columns - _table_columns(conn, table_name)
    if missing_columns:
        missing = ', '.join(sorted(missing_columns))
        raise RuntimeError(
            f'La tabella {table_name} ha uno schema legacy non riconosciuto. '
            f'Colonne strutturali mancanti: {missing}.'
        )


def ensure_schema(conn):
    """Create the sleep-call tables and update additive legacy columns."""
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS call_sonno (
            id INTEGER NOT NULL PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            telefono VARCHAR(20) NOT NULL,
            email VARCHAR(100) NOT NULL,
            eta_bambino_mesi INTEGER NOT NULL,
            difficolta_principale VARCHAR(120) NOT NULL,
            difficolta_altro VARCHAR(300),
            consenso_privacy BOOLEAN DEFAULT 0 NOT NULL,
            data VARCHAR(20) NOT NULL,
            ora VARCHAR(10) NOT NULL,
            stato VARCHAR(20) DEFAULT 'In attesa' NOT NULL,
            google_event_id VARCHAR(255),
            formula_scelta VARCHAR(30),
            token_questionario VARCHAR(96),
            questionario_inviato_il DATETIME,
            creato_il DATETIME NOT NULL,
            aggiornato_il DATETIME NOT NULL,
            UNIQUE (token_questionario)
        )
        """
    )
    _require_core_columns(conn, 'call_sonno', CALL_SONNO_CORE_COLUMNS)
    _add_missing_columns(conn, 'call_sonno', CALL_SONNO_ADDITIVE_COLUMNS)
    conn.execute(
        "UPDATE call_sonno SET creato_il = CURRENT_TIMESTAMP WHERE creato_il IS NULL"
    )
    conn.execute(
        "UPDATE call_sonno SET aggiornato_il = CURRENT_TIMESTAMP WHERE aggiornato_il IS NULL"
    )
    conn.execute('CREATE INDEX IF NOT EXISTS ix_call_sonno_data ON call_sonno (data)')
    conn.execute('CREATE INDEX IF NOT EXISTS ix_call_sonno_stato ON call_sonno (stato)')
    conn.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS ix_call_sonno_token_questionario '
        'ON call_sonno (token_questionario)'
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questionario_sonno (
            id INTEGER NOT NULL PRIMARY KEY,
            call_sonno_id INTEGER NOT NULL UNIQUE,
            risposte TEXT NOT NULL,
            consenso_dati_sanitari BOOLEAN DEFAULT 0 NOT NULL,
            consenso_marketing BOOLEAN DEFAULT 0 NOT NULL,
            compilato_il DATETIME NOT NULL,
            FOREIGN KEY(call_sonno_id) REFERENCES call_sonno (id)
        )
        """
    )
    _require_core_columns(
        conn,
        'questionario_sonno',
        QUESTIONARIO_SONNO_CORE_COLUMNS,
    )
    _add_missing_columns(
        conn,
        'questionario_sonno',
        QUESTIONARIO_SONNO_ADDITIVE_COLUMNS,
    )
    conn.execute(
        "UPDATE questionario_sonno SET compilato_il = CURRENT_TIMESTAMP "
        "WHERE compilato_il IS NULL"
    )


def main():
    if not os.path.exists(PERCORSO_DB):
        print('Database SQLite non presente: lo schema verrà creato al primo avvio.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    try:
        ensure_schema(conn)
        conn.commit()
    finally:
        conn.close()
    print('Tabelle call_sonno e questionario_sonno verificate/aggiornate.')


if __name__ == '__main__':
    main()
