"""
Script di migrazione UNA TANTUM.

Aggiunge la colonna `google_event_id` alla tabella `appuntamento` di un
database SQLite già esistente. Serve perché `db.create_all()` crea solo le
tabelle mancanti: NON aggiunge colonne nuove a tabelle già esistenti.

Uso:
    python3 migrazione_google_event_id.py

Lo script è sicuro da eseguire più volte: se la colonna esiste già non fa
nulla. Esegui questo comando UNA VOLTA, dopo aver aggiornato app.py e PRIMA
di riavviare il sito con il nuovo codice.

Se invece stai partendo da un database nuovo/vuoto (nessun dato reale da
conservare), puoi anche semplicemente cancellare il file appuntamenti.db:
verrà ricreato automaticamente con lo schema aggiornato al primo avvio.
"""
import sqlite3
import os

PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


def main():
    if not os.path.exists(PERCORSO_DB):
        print(f'Nessun database trovato in {PERCORSO_DB}: verrà creato automaticamente '
              f'con lo schema aggiornato al primo avvio del sito. Nessuna azione necessaria.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(appuntamento)")
    colonne = [riga[1] for riga in cur.fetchall()]

    if 'google_event_id' in colonne:
        print('La colonna google_event_id esiste già: nessuna modifica necessaria.')
    else:
        cur.execute("ALTER TABLE appuntamento ADD COLUMN google_event_id VARCHAR(255)")
        conn.commit()
        print('Colonna google_event_id aggiunta con successo alla tabella appuntamento.')

    conn.close()


if __name__ == '__main__':
    main()
