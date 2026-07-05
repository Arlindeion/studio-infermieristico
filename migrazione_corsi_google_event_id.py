"""
Script di migrazione UNA TANTUM.

Aggiunge le colonne `tipo`, `durata_ore` e `google_event_id` alla tabella
`corso` di un database SQLite già esistente. Servono per collegare i corsi
creati in /admin agli eventi generati su Google Calendar con la durata corretta.

Uso:
    python3 migrazione_corsi_google_event_id.py

Lo script è sicuro da eseguire più volte: se le colonne esistono già non fa
nulla. Esegui questo comando UNA VOLTA, dopo aver aggiornato app.py e PRIMA
di riavviare il sito con il nuovo codice.
"""
import os
import sqlite3


PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


def aggiungi_colonna_se_manca(cur, conn, colonne, nome, definizione):
    if nome in colonne:
        print(f'La colonna {nome} esiste già nella tabella corso: nessuna modifica necessaria.')
        return
    cur.execute(f'ALTER TABLE corso ADD COLUMN {nome} {definizione}')
    conn.commit()
    print(f'Colonna {nome} aggiunta con successo alla tabella corso.')


def main():
    if not os.path.exists(PERCORSO_DB):
        print(f'Nessun database trovato in {PERCORSO_DB}: verrà creato automaticamente '
              f'con lo schema aggiornato al primo avvio del sito. Nessuna azione necessaria.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(corso)")
    colonne = [riga[1] for riga in cur.fetchall()]

    if not colonne:
        print('La tabella corso non esiste ancora: verrà creata automaticamente al primo avvio del sito.')
    else:
        aggiungi_colonna_se_manca(cur, conn, colonne, 'tipo', 'VARCHAR(100)')
        colonne.append('tipo')
        aggiungi_colonna_se_manca(cur, conn, colonne, 'durata_ore', 'FLOAT DEFAULT 2')
        colonne.append('durata_ore')
        aggiungi_colonna_se_manca(cur, conn, colonne, 'google_event_id', 'VARCHAR(255)')

    conn.close()


if __name__ == '__main__':
    main()
