# S.C. Studio Infermieristico — sito web

Applicazione Flask con sito pubblico, prenotazione delle prestazioni infermieristiche, iscrizione ai corsi e area amministrativa.

Il contesto dell'attività, l'identità e le priorità non sono duplicati in questo file. Prima di intervenire sul progetto leggere [AGENTS.md](AGENTS.md) e l'indice in [docs/README.md](docs/README.md).

## Stack

- Python 3.14 e Flask 3
- SQLAlchemy ORM e Flask-Migrate
- SQLite in locale, PostgreSQL tramite `DATABASE_URL`
- Flask-Login, Flask-Mail, Flask-Limiter e Flask-Talisman
- APScheduler e integrazione Google Calendar
- Jinja2, CSS e JavaScript vanilla
- pytest

## Avvio locale

### macOS e Linux

```bash
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m flask --app app run
```

### Windows

```powershell
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m flask --app app run
```

Il sito sarà disponibile su `http://127.0.0.1:5000`.

## Configurazione

Creare un file `.env` locale senza commetterlo. Le variabili supportate sono:

```dotenv
SECRET_KEY=
FLASK_ENV=development
DATABASE_URL=

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

GOOGLE_CALENDAR_ICS_URL=
CALENDARIO_CACHE_SECONDI=300
GOOGLE_SERVICE_ACCOUNT_FILE=
GOOGLE_CALENDAR_ID=
GOOGLE_ANALYTICS_ID=
```

`DATABASE_URL` è facoltativa: senza questa variabile viene utilizzato `appuntamenti.db`. Gli URL `postgres://` e `postgresql://` vengono normalizzati per il driver `psycopg`.

Per generare una chiave applicativa:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Non inserire mai nel repository `.env`, database reali, URL iCal privati o file JSON di account di servizio.

## Test e controlli

```bash
pytest
git diff --check
```

Per una modifica pubblica applicare anche la checklist visuale, di accessibilità e SEO descritta in [AGENTS.md](AGENTS.md).

## Migrazioni

Per aggiornare una copia SQLite esistente creata prima dell'introduzione delle funzioni gestionali, eseguire una sola volta e nell'ordine:

```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
```

Non servono per un database creato da zero. Prima di portare in produzione un database PostgreSQL con dati reali, generare e verificare le migrazioni Alembic invece di affidarsi a `db.create_all()`.

Le procedure e le integrazioni sono documentate in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Struttura essenziale

```text
app.py                 applicazione, modelli, route, email e scheduler
config.py              configurazioni development/production/testing
templates/             pagine e componenti Jinja2
static/css/            token, base, componenti e moduli di pagina
static/js/             comportamento client compatibile con la CSP
static/img/            logo e fotografie
tests/                 suite pytest
docs/                  memoria strategica, funzionale e visiva
migrazione_*.py        migrazioni SQLite una tantum
```

I fogli di stile sono separati per responsabilità: `tokens.css`, `base.css` e `components.css` costituiscono il nucleo condiviso; `homepage.css`, `consulenza.css` e `admin.css` vengono caricati soltanto dove servono. Evitare `@import` e nuove sezioni versionate in coda ai file.

## Area amministrativa

Il login locale è disponibile su `http://127.0.0.1:5000/admin/login`.

Su un database vuoto l'applicazione crea ancora l'utente iniziale `admin` con password `cambiami123`. La password deve essere cambiata prima di qualsiasi esposizione pubblica; la rimozione di questa credenziale predefinita è indicata come attività pre-lancio nella roadmap.

## Documentazione

- [Brief del progetto](docs/PROJECT_BRIEF.md)
- [Identità visiva e verbale](docs/BRAND_SYSTEM.md)
- [Mappa del sito e flussi](docs/SITE_MAP_AND_FLOWS.md)
- [Roadmap](docs/ROADMAP.md)
- [Registro delle decisioni](docs/DECISIONS.md)
- [Contenuti e fotografie](docs/CONTENT_AND_ASSETS.md)
- [Locandine e materiali commerciali](docs/locandine.md)
- [Operatività tecnica](docs/OPERATIONS.md)
