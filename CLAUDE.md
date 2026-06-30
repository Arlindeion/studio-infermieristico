# Studio Infermieristico

## Stack tecnologico
- Flask
- SQLAlchemy
- SQLite
- Flask-Login
- Flask-Mail
- Jinja2
- HTML/CSS/JavaScript vanilla

## Regole del progetto
- Non utilizzare framework frontend.
- Mantenere il rendering server-side con Jinja2.
- Utilizzare SQLAlchemy ORM.
- Evitare dipendenze non necessarie.
- Privilegiare codice semplice e leggibile.
- Variabili sensibili (SECRET_KEY, MAIL_PASSWORD) sempre in `.env`, mai hardcoded.

## Convenzioni
- Codice Python in inglese.
- Interfaccia utente in italiano.
- Commenti solo se realmente utili.
- Preferire funzioni piccole e riutilizzabili.

## Struttura
- templates/: template Jinja2
- static/css/: fogli di stile
- static/img/: immagini e logo
- app.py: applicazione Flask principale
- JavaScript: file separati in static/js/ (externalizzati per CSP)