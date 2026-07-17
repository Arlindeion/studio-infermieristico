import sqlite3

from migrazione_call_sonno import ensure_schema


def test_ensure_schema_updates_an_existing_call_table_without_losing_rows():
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute(
            """
            CREATE TABLE call_sonno (
                id INTEGER NOT NULL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                telefono VARCHAR(20) NOT NULL,
                email VARCHAR(100) NOT NULL,
                eta_bambino_mesi INTEGER NOT NULL,
                difficolta_principale VARCHAR(120) NOT NULL,
                data VARCHAR(20) NOT NULL,
                ora VARCHAR(10) NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO call_sonno (
                nome, telefono, email, eta_bambino_mesi,
                difficolta_principale, data, ora
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ('Test', '0000000', 'test@example.com', 6, 'Risvegli', '2026-09-01', '09:00'),
        )

        ensure_schema(conn)
        ensure_schema(conn)

        columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info("call_sonno")')
        }
        row = conn.execute(
            """
            SELECT consenso_privacy, stato, creato_il, aggiornato_il
            FROM call_sonno
            """
        ).fetchone()

        assert 'consenso_privacy' in columns
        assert 'token_questionario' in columns
        assert row[0] == 0
        assert row[1] == 'In attesa'
        assert row[2] is not None
        assert row[3] is not None
        assert conn.execute('SELECT COUNT(*) FROM call_sonno').fetchone()[0] == 1
    finally:
        conn.close()
