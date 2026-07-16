"""Migrazione una tantum per SQLite: call sonno e questionario riservato.

Uso, dopo un backup del database reale:
    python3 migrazione_call_sonno.py

Per PostgreSQL generare e revisionare una migrazione Flask-Migrate/Alembic.
"""
import os
import sqlite3


PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


def main():
    if not os.path.exists(PERCORSO_DB):
        print('Database SQLite non presente: lo schema verrà creato al primo avvio.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    try:
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
        conn.execute('CREATE INDEX IF NOT EXISTS ix_call_sonno_data ON call_sonno (data)')
        conn.execute('CREATE INDEX IF NOT EXISTS ix_call_sonno_stato ON call_sonno (stato)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_call_sonno_token_questionario ON call_sonno (token_questionario)')
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
        conn.commit()
    finally:
        conn.close()
    print('Tabelle call_sonno e questionario_sonno verificate/create.')


if __name__ == '__main__':
    main()
