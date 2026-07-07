"""
Script di migrazione UNA TANTUM.

Crea la tabella `registro_evento` in un database SQLite gia esistente. Serve
per tracciare errori parziali e sincronizzazioni operative senza affidarsi solo
al file app.log.

Uso:
    python3 migrazione_registro_eventi.py

Lo script e' sicuro da eseguire piu' volte: se la tabella esiste gia non fa
nulla. Esegui questo comando UNA VOLTA, dopo aver aggiornato app.py e PRIMA
di riavviare il sito con il nuovo codice, se stai conservando dati reali.
"""
import os
import sqlite3


PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


def main():
    if not os.path.exists(PERCORSO_DB):
        print(f'Nessun database trovato in {PERCORSO_DB}: verra creato automaticamente '
              f'con lo schema aggiornato al primo avvio del sito. Nessuna azione necessaria.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registro_evento (
            id INTEGER NOT NULL,
            categoria VARCHAR(40) NOT NULL,
            esito VARCHAR(20) DEFAULT 'info' NOT NULL,
            messaggio TEXT NOT NULL,
            entita_tipo VARCHAR(80),
            entita_id INTEGER,
            dettagli TEXT,
            creato_il DATETIME,
            PRIMARY KEY (id)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS ix_registro_evento_categoria ON registro_evento (categoria)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_registro_evento_esito ON registro_evento (esito)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_registro_evento_entita_tipo ON registro_evento (entita_tipo)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_registro_evento_entita_id ON registro_evento (entita_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_registro_evento_creato_il ON registro_evento (creato_il)")
    conn.commit()
    conn.close()
    print('Tabella registro_evento verificata/creata.')


if __name__ == '__main__':
    main()
