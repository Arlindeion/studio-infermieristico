"""
Script di migrazione UNA TANTUM.

Aggiunge le colonne necessarie per collegare le iscrizioni ai corsi alle
singole date create in admin e per distinguere open day, richieste di
iscrizione e richieste di ricontatto. Crea anche la rubrica interna delle
famiglie/partecipanti, il modulo privato del percorso di accompagnamento alla
nascita e collega le iscrizioni esistenti al contatto salvato.

Uso:
    python3 migrazione_gestione_iscritti_corsi.py

Lo script e' sicuro da eseguire piu' volte: se le colonne esistono gia' non fa
nulla. Esegui questo comando UNA VOLTA, dopo aver aggiornato app.py e PRIMA
di riavviare il sito con il nuovo codice.
"""
import os
import sqlite3
import json
from datetime import datetime


PERCORSO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appuntamenti.db')


def colonne_tabella(cur, nome_tabella):
    cur.execute(f"PRAGMA table_info({nome_tabella})")
    return [riga[1] for riga in cur.fetchall()]


def tabella_esiste(cur, nome_tabella):
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (nome_tabella,))
    return cur.fetchone() is not None


def aggiungi_colonna_se_manca(cur, conn, tabella, colonne, nome, definizione):
    if nome in colonne:
        print(f'La colonna {nome} esiste gia nella tabella {tabella}: nessuna modifica necessaria.')
        return colonne
    cur.execute(f'ALTER TABLE {tabella} ADD COLUMN {nome} {definizione}')
    conn.commit()
    print(f'Colonna {nome} aggiunta con successo alla tabella {tabella}.')
    return colonne + [nome]


def crea_tabella_persona_corso(cur, conn):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS persona_corso (
            id INTEGER NOT NULL,
            nome VARCHAR(100) NOT NULL,
            telefono VARCHAR(20) NOT NULL,
            email VARCHAR(100),
            codice_fiscale VARCHAR(32),
            nome_bambino VARCHAR(100),
            eta_bambino VARCHAR(40),
            note TEXT,
            creato_il DATETIME,
            aggiornato_il DATETIME,
            PRIMARY KEY (id)
        )
        """
    )
    conn.commit()
    print('Tabella persona_corso verificata/creata.')


def crea_tabelle_percorso_accompagnamento(cur, conn):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS percorso_accompagnamento (
            id INTEGER NOT NULL,
            titolo VARCHAR(200) NOT NULL,
            slug VARCHAR(120) NOT NULL,
            descrizione TEXT,
            capienza_coppie INTEGER,
            luogo VARCHAR(200),
            contatti VARCHAR(200),
            stato VARCHAR(20) DEFAULT 'Aperto' NOT NULL,
            creato_il DATETIME,
            PRIMARY KEY (id),
            UNIQUE (slug)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS incontro_accompagnamento (
            id INTEGER NOT NULL,
            percorso_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            data VARCHAR(20) NOT NULL,
            ora VARCHAR(10),
            professionista VARCHAR(100) NOT NULL,
            tema VARCHAR(200) NOT NULL,
            luogo VARCHAR(200),
            note TEXT,
            creato_il DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(percorso_id) REFERENCES percorso_accompagnamento (id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS presenza_accompagnamento (
            id INTEGER NOT NULL,
            iscrizione_id INTEGER NOT NULL,
            incontro_id INTEGER NOT NULL,
            presente BOOLEAN,
            note TEXT,
            aggiornata_il DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(iscrizione_id) REFERENCES iscrizione_corso (id),
            FOREIGN KEY(incontro_id) REFERENCES incontro_accompagnamento (id)
        )
        """
    )
    conn.commit()
    print('Tabelle percorso_accompagnamento, incontro_accompagnamento e presenza_accompagnamento verificate/create.')


def trova_persona(cur, telefono, email):
    email = (email or '').strip().lower()
    telefono = (telefono or '').strip()
    if email:
        cur.execute("SELECT id FROM persona_corso WHERE lower(email) = ?", (email,))
        risultato = cur.fetchone()
        if risultato:
            return risultato[0]
    if telefono:
        cur.execute("SELECT id FROM persona_corso WHERE telefono = ?", (telefono,))
        risultato = cur.fetchone()
        if risultato:
            return risultato[0]
    return None


def popola_rubrica_da_iscrizioni(cur, conn, colonne_iscrizione):
    if 'persona_id' not in colonne_iscrizione:
        return

    cur.execute(
        """
        SELECT id, nome, telefono, email, codice_fiscale, dati_extra
        FROM iscrizione_corso
        WHERE persona_id IS NULL
        """
    )
    iscrizioni = cur.fetchall()
    if not iscrizioni:
        print('Nessuna iscrizione esistente da collegare alla rubrica.')
        return

    ora = datetime.now().isoformat(sep=' ', timespec='seconds')
    collegamenti = 0
    for iscrizione in iscrizioni:
        iscrizione_id, nome, telefono, email, codice_fiscale, dati_extra = iscrizione
        extra = {}
        if dati_extra:
            try:
                extra = json.loads(dati_extra)
            except json.JSONDecodeError:
                extra = {}

        persona_id = trova_persona(cur, telefono, email)
        if not persona_id:
            cur.execute(
                """
                INSERT INTO persona_corso
                    (nome, telefono, email, codice_fiscale, nome_bambino, eta_bambino, creato_il, aggiornato_il)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nome or 'Contatto senza nome',
                    telefono or 'Non indicato',
                    email or None,
                    codice_fiscale or None,
                    extra.get('nome_bambino') or None,
                    extra.get('eta_bambino') or None,
                    ora,
                    ora,
                )
            )
            persona_id = cur.lastrowid

        cur.execute(
            "UPDATE iscrizione_corso SET persona_id = ? WHERE id = ?",
            (persona_id, iscrizione_id)
        )
        collegamenti += 1

    conn.commit()
    print(f'Rubrica popolata/collegata per {collegamenti} iscrizioni corso.')


def main():
    if not os.path.exists(PERCORSO_DB):
        print(f'Nessun database trovato in {PERCORSO_DB}: verra creato automaticamente '
              f'con lo schema aggiornato al primo avvio del sito. Nessuna azione necessaria.')
        return

    conn = sqlite3.connect(PERCORSO_DB)
    cur = conn.cursor()

    crea_tabella_persona_corso(cur, conn)
    crea_tabelle_percorso_accompagnamento(cur, conn)

    colonne_corso = colonne_tabella(cur, 'corso') if tabella_esiste(cur, 'corso') else []
    if colonne_corso:
        colonne_corso = aggiungi_colonna_se_manca(
            cur, conn, 'corso', colonne_corso, 'capienza_massima', 'INTEGER'
        )
        colonne_corso = aggiungi_colonna_se_manca(
            cur, conn, 'corso', colonne_corso, 'stato', "VARCHAR(20) DEFAULT 'Aperto' NOT NULL"
        )
    else:
        print('La tabella corso non esiste ancora: verra creata automaticamente al primo avvio del sito.')

    colonne_iscrizione = colonne_tabella(cur, 'iscrizione_corso') if tabella_esiste(cur, 'iscrizione_corso') else []
    if colonne_iscrizione:
        colonne_iscrizione = aggiungi_colonna_se_manca(
            cur, conn, 'iscrizione_corso', colonne_iscrizione, 'corso_id', 'INTEGER'
        )
        colonne_iscrizione = aggiungi_colonna_se_manca(
            cur, conn, 'iscrizione_corso', colonne_iscrizione, 'persona_id', 'INTEGER'
        )
        colonne_iscrizione = aggiungi_colonna_se_manca(
            cur, conn, 'iscrizione_corso', colonne_iscrizione, 'percorso_accompagnamento_id', 'INTEGER'
        )
        colonne_iscrizione = aggiungi_colonna_se_manca(
            cur, conn, 'iscrizione_corso', colonne_iscrizione, 'tipo_richiesta',
            "VARCHAR(40) DEFAULT 'richiesta_iscrizione' NOT NULL"
        )
        colonne_iscrizione = aggiungi_colonna_se_manca(
            cur, conn, 'iscrizione_corso', colonne_iscrizione, 'posti', 'INTEGER DEFAULT 1 NOT NULL'
        )
        cur.execute(
            """
            UPDATE iscrizione_corso
            SET tipo_richiesta = 'open_day'
            WHERE corso_tipo = 'accompagnamento-nascita'
              AND tipo_richiesta = 'richiesta_iscrizione'
            """
        )
        cur.execute(
            """
            UPDATE iscrizione_corso
            SET tipo_richiesta = 'ricontatto', posti = 0
            WHERE data_corso = 'Da ricontattare per prossime date'
            """
        )
        conn.commit()
        print('Valori predefiniti delle iscrizioni corso aggiornati.')
        popola_rubrica_da_iscrizioni(cur, conn, colonne_iscrizione)
    else:
        print('La tabella iscrizione_corso non esiste ancora: verra creata automaticamente al primo avvio del sito.')

    conn.close()


if __name__ == '__main__':
    main()
