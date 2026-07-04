# Studio Infermieristico

## Stack tecnologico
- Python 3.14 + Flask
- SQLAlchemy (ORM) + SQLite
- Flask-Login, Flask-Mail, Flask-Limiter, Flask-Talisman
- APScheduler (promemoria 24h)
- Jinja2 + HTML/CSS/JavaScript vanilla

## Regole del progetto
- No framework frontend.
- Mantenere il rendering server-side con Jinja2.
- Utilizzare SQLAlchemy ORM (no SQL grezzo).
- Evitare dipendenze non necessarie.
- Privilegiare codice semplice e leggibile.
- Variabili sensibili (SECRET_KEY, MAIL_PASSWORD) sempre in `.env`, mai hardcoded.
- Codice Python in inglese; interfaccia utente in italiano.
- Commenti solo se realmente utili.
- Preferire funzioni piccole e riutilizzabili.

## Comandi utili
- Attiva ambiente: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
- Installa dipendenze: `pip install -r requirements.txt`
- Avvia in locale: `python3 -m flask --app app run` → http://127.0.0.1:5000
- Test: `pytest`
- Aggiorna requirements: `pip freeze > requirements.txt`

## Variabili d'ambiente (`.env`, NON committed)
- `SECRET_KEY` — chiave segreta Flask (genera con `python -c "import secrets; print(secrets.token_hex(32))"`)
- `MAIL_USERNAME` — indirizzo Gmail usato per inviare le email
- `MAIL_PASSWORD` — app-password Gmail (16 caratteri)
- `FLASK_ENV` — `development` | `production` | `testing` (default: `development`)
- `GOOGLE_CALENDAR_ICS_URL` — indirizzo segreto in formato iCal del calendario Google sincronizzato da Arzamed (Impostazioni calendario → Integra calendario). Se non impostata, il sito funziona comunque ma non conosce gli impegni presi solo su Arzamed.
- `CALENDARIO_CACHE_SECONDI` — per quanti secondi tenere in cache il calendario scaricato prima di ricontattare Google (default: `300`, cioè 5 minuti)

## Struttura
- `app.py` — applicazione Flask principale (modelli, route, email, scheduler)
- `config.py` — classi di configurazione (Development / Production / Testing)
- `requirements.txt` — dipendenze
- `templates/` — template Jinja2 (`base.html` è il layout comune)
- `static/css/stile.css` — foglio di stile
- `static/js/` — JavaScript externalizzato per CSP (calendario, carosello, form, menu mobile, admin)
- `static/img/` — logo e foto
- `tests/test_app.py` — test con pytest (db in memoria)
- `instance/` — cartella di istanza Flask (db legacy, ignorare)
- `appuntamenti.db` — database SQLite (auto-creato al primo avvio)

## Modelli / dominio
- `Admin` — utente area admin (Flask-Login)
- `Appuntamento` — prenotazione paziente. `stato` ∈ {`In attesa`, `Confermato`, `Annullato`}
- `Corso` — evento mostrato in homepage
- Admin default: `admin` / `cambiami123` (creato da `app.py` se il DB è vuoto)

## Sicurezza
- CSRF gestito manualmente via `_csrf_token` di sessione (`generate_csrf_token`), validato in `prenota` e `login`.
- Rate limiting su `prenota` e `login` (`Flask-Limiter`).
- Header di sicurezza via `Flask-Talisman`; cookie di sessione sicuri in produzione.
