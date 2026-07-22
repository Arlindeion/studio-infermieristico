# S.C. Studio Infermieristico — sito web

Applicazione Flask con sito pubblico, prenotazione delle prestazioni infermieristiche, iscrizione ai corsi, call e questionario della consulenza del sonno e area amministrativa.

Il contesto dell'attività, l'identità e le priorità non sono duplicati in questo file. Prima di intervenire sul progetto leggere [AGENTS.md](AGENTS.md) e l'indice in [docs/README.md](docs/README.md).

## Stack

- Python 3.14 e Flask 3
- SQLAlchemy ORM e Flask-Migrate
- SQLite in locale, PostgreSQL tramite `DATABASE_URL`
- Flask-Login, Flask-Mail, Flask-Limiter e Flask-Talisman
- APScheduler e integrazione Google Calendar
- Jinja2, CSS e JavaScript vanilla
- pytest
- Node.js, usato solo dal test comportamentale del menu senza dipendenze npm

## Avvio locale

### macOS e Linux

```bash
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m flask --app app db upgrade
python3 -m flask --app app run
```

### Windows

```powershell
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m flask --app app db upgrade
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
MAIL_USE_SSL=false
MAIL_SUPPRESS_SEND=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
MAIL_ADMIN_RECIPIENT=

GOOGLE_CALENDAR_ICS_URL=
CALENDARIO_CACHE_SECONDI=300
GOOGLE_SERVICE_ACCOUNT_FILE=
GOOGLE_CALENDAR_ID=
GOOGLE_ANALYTICS_ID=
SONNO_CALL_URL=

APP_ENV=development
ADMIN_BOOTSTRAP_USERNAME=
ADMIN_BOOTSTRAP_PASSWORD=
STAGING_AUTH_USERNAME=
STAGING_AUTH_PASSWORD=
```

`DATABASE_URL` è facoltativa: senza questa variabile viene utilizzato `appuntamenti.db`. Gli URL `postgres://` e `postgresql://` vengono normalizzati per il driver `psycopg`.

Per generare una chiave applicativa:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Non inserire mai nel repository `.env`, database reali, URL iCal privati o file JSON di account di servizio.
Usare [`.env.example`](.env.example)
come elenco delle chiavi, mai come contenitore dei valori reali.

## Render

Il file `render.yaml` descrive lo staging gratuito approvato: Web Service e
PostgreSQL nella regione di Francoforte, HTTPS gestito, health check su
`/healthz`, auto-deploy disattivato e valori sensibili richiesti nel pannello.
Lo staging è protetto da Basic Auth e non indicizzabile. Non sincronizzare il
contenuto del file `.env` locale con Render: inserire soltanto i segreti previsti
dalla procedura in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Test e controlli

```bash
pytest
git diff --check
```

Per una modifica pubblica applicare anche la checklist visuale, di accessibilità e SEO descritta in [AGENTS.md](AGENTS.md).

## Migrazioni

Alembic è la fonte dello schema per ogni database nuovo:

```bash
flask --app app db upgrade
```

L'avvio dell'applicazione non esegue `db.create_all()`. Dopo una modifica ai
modelli generare una revisione, controllarla manualmente e verificarla:

```bash
flask --app app db migrate -m "descrizione"
flask --app app db upgrade
flask --app app db check
```

Per aggiornare una copia SQLite esistente creata prima dell'introduzione delle funzioni gestionali, eseguire una sola volta e nell'ordine:

```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
python3 migrazione_call_sonno.py
```

Non servono per un database creato da zero. Un database legacy già allineato
allo schema corrente può adottare la baseline con `flask --app app db stamp
head`, ma soltanto dopo backup e confronto dello schema: `stamp` non modifica le
tabelle. Non eseguire `upgrade` direttamente su un database legacy non marcato,
perché Alembic tenterebbe di creare tabelle già presenti.

Le procedure e le integrazioni sono documentate in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Backup PostgreSQL

Gli script [backup_postgres.sh](scripts/backup_postgres.sh) e
[restore_postgres.sh](scripts/restore_postgres.sh) creano dump PostgreSQL
cifrati, verificano il checksum e consentono il ripristino soltanto verso un
database vuoto. Non salvano URL, password o dati nel repository. Frequenza,
conservazione, Portachiavi macOS e collaudo periodico sono descritti in
[docs/OPERATIONS.md](docs/OPERATIONS.md).

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

L'applicazione non crea credenziali predefinite. Per creare interattivamente il
primo amministratore in locale:

```bash
flask --app app db upgrade
flask --app app create-admin
```

La password deve contenere almeno 16 caratteri. Su un database di produzione
vuoto impostare temporaneamente `ADMIN_BOOTSTRAP_USERNAME` e
`ADMIN_BOOTSTRAP_PASSWORD` nel gestore dei segreti prima del primo avvio, quindi
rimuoverle dopo aver verificato l'accesso. Se mancano, l'avvio di produzione si
interrompe invece di creare un account prevedibile.

## Documentazione

- [Brief del progetto](docs/PROJECT_BRIEF.md)
- [Identità visiva e verbale](docs/BRAND_SYSTEM.md)
- [Mappa del sito e flussi](docs/SITE_MAP_AND_FLOWS.md)
- [Roadmap](docs/ROADMAP.md)
- [Registro delle decisioni](docs/DECISIONS.md)
- [Contenuti e fotografie](docs/CONTENT_AND_ASSETS.md)
- [Locandine e materiali commerciali](docs/locandine.md)
- [Operatività tecnica](docs/OPERATIONS.md)
