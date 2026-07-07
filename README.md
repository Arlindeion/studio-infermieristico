# S.C. Studio Infermieristico — Sito Web

Sito web ufficiale di S.C. Studio Infermieristico con sistema di prenotazione appuntamenti, gestione corsi e area admin protetta.

---

## Posizionamento marketing

- **Brand:** S.C. Studio Infermieristico è la sede; per famiglie e neogenitori il riferimento umano è Selene.
- **Percezione desiderata:** chi entra nel sito deve capire rapidamente che Selene è una professionista sanitaria competente, concreta e vicina ai genitori; una scelta autorevole per corsi, consulenze e primi mesi del bambino.
- **Priorità commerciale iniziale:** corsi in presenza e contatti qualificati. Le prestazioni infermieristiche restano prenotabili ma non sono il focus principale della crescita.
- **Target primario:** neomamme stanche e genitori preoccupati. Target attivi anche coppie alla prima gravidanza, nonni e caregiver. Aziende e gruppi sono target secondari da gestire quando arrivano.
- **Consulenze online:** potenzialmente rivolte a famiglie in tutta Italia, con call conoscitiva gratuita prima di eventuali percorsi o pagamenti.
- **Tono:** guida calma e competente, non promessa miracolosa. Evitare frasi che facciano pensare a risultati garantiti o soluzioni immediate per tutti.
- **Naming:** `Corso di accompagnamento alla nascita` e `Disostruzione pediatrica e tagli sicuri` restano nomi ufficiali. `SOS neomamma` va evoluto verso un nome più calmo, come `Supporto primi mesi`, mantenendo nei testi le keyword consulenze neogenitori, sonno, spannolinamento e ciuccio.
- **CTA:** privilegiare richieste informazioni e contatti qualificati. La call conoscitiva gratuita per le consulenze deve comparire anche in homepage. I prezzi non sono una leva principale nella fase iniziale.
- **Differenza competitiva:** il corso di accompagnamento alla nascita valorizza 5 professionisti sanitari: infermiera, ostetrica, psicologa, osteopata e nutrizionista.

---

## Stack tecnologico

- **Backend:** Python 3.14 + Flask
- **Database:** SQLite locale / PostgreSQL-ready in produzione + SQLAlchemy
- **Autenticazione:** Flask-Login
- **Rate Limiting:** Flask-Limiter
- **Email:** Flask-Mail + Gmail SMTP
- **Frontend:** HTML, CSS, JavaScript vanilla

---

## Struttura del progetto
studio-infermieristico/

├── app.py                          # Logica principale Flask

├── .env                            # Variabili d'ambiente (NON su GitHub)

├── .gitignore                      # File esclusi da Git

├── requirements.txt                # Dipendenze Python

├── static/

│   ├── css/

│   │   └── stile.css              # Stile del sito

│   └── img/                       # Immagini e logo

└── templates/

├── base.html                  # Template base (header, footer)

├── homepage.html              # Homepage

├── chi_siamo.html             # Pagina Chi Sono

├── prima_della_nascita.html   # Pagina Prima della nascita

├── dopo_la_nascita.html       # Pagina Dopo la nascita

├── consulenze_online.html     # Pagina Consulenze online

├── prestazioni_infermieristiche.html

├── prenota.html               # Form prenotazione

├── conferma.html              # Conferma prenotazione

├── privacy.html               # Informativa privacy

├── login.html                 # Login area admin

├── admin.html                 # Dashboard admin

└── modifica_appuntamento.html # Modifica appuntamento

---

## Installazione su un nuovo dispositivo

### Mac

```bash
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows

```bash
git clone https://github.com/Arlindeion/studio-infermieristico.git
cd studio-infermieristico
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configurazione variabili d'ambiente

Crea un file `.env` nella cartella del progetto con questi valori:
SECRET_KEY=genera_una_chiave_con_python_secrets

MAIL_USERNAME=sc.studioinfermieristico@gmail.com

MAIL_PASSWORD=app_password_gmail_16_caratteri

GOOGLE_CALENDAR_ICS_URL=indirizzo_segreto_ical_del_calendario_arzamed

GOOGLE_SERVICE_ACCOUNT_FILE=percorso/al/file-chiave-service-account.json

GOOGLE_CALENDAR_ID=id_del_calendario_google

GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX

DATABASE_URL=postgresql://utente:password@host:porta/database

Se `DATABASE_URL` non è impostata, il sito usa automaticamente `appuntamenti.db`
in SQLite. Gli URL PostgreSQL forniti dagli hosting come `postgres://...` o
`postgresql://...` vengono normalizzati automaticamente per usare il driver
`psycopg`.

Per generare una SECRET_KEY sicura:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Avvio del sito in locale

### Mac

```bash
source venv/bin/activate
python3 -m flask --app app run
```

### Windows

```bash
venv\Scripts\activate
python -m flask --app app run
```

Apri il browser su: **http://127.0.0.1:5000**

---

## Area Admin

- **URL login:** http://127.0.0.1:5000/admin/login
- **Credenziali default:** admin / cambiami123
- Cambia la password al primo accesso

---

## Migrazioni database

Se aggiorni un database `appuntamenti.db` già esistente dopo un pull, esegui una volta:

```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
```

La terza migrazione aggiorna anche la gestione iscritti: date corso, stati/capienze, rubrica famiglie/partecipanti, modulo privato del percorso di accompagnamento alla nascita, incontri, presenze e collegamento tra iscrizioni e persona salvata. Non serve su un database nuovo creato da zero.
La quarta crea il registro eventi per tracciare errori parziali, email non inviate e sincronizzazioni Google Calendar.

Il progetto è predisposto per Flask-Migrate/Alembic. In locale puoi continuare
a usare SQLite; prima del deploy su PostgreSQL conviene generare e verificare
le migrazioni con:

```bash
flask db init
flask db migrate -m "schema iniziale"
flask db upgrade
```

---

## Aggiornare GitHub dopo le modifiche

```bash
git salva "descrizione delle modifiche"
```

Oppure manualmente:

```bash
git add .
git commit -m "descrizione delle modifiche"
git push
```

---

## Scaricare le ultime modifiche su un secondo dispositivo

```bash
git pull
```

Da eseguire sempre prima di iniziare a lavorare su un dispositivo diverso.

---

## Generare il file requirements.txt

Se installi nuovi pacchetti aggiorna il file con:

```bash
pip freeze > requirements.txt
```

---

## Note importanti

- Il file `.env` non è su GitHub — va ricreato manualmente su ogni dispositivo
- Il database `appuntamenti.db` non è su GitHub — viene creato automaticamente al primo avvio
- In produzione puoi usare PostgreSQL impostando `DATABASE_URL`
- Le immagini in `static/img/` sono su GitHub — verificare che ci siano tutte dopo il clone

---

## Testing

To run the test suite:

```bash
pip install pytest
pytest
```

## Configuration

The application uses a configuration class defined in `config.py`. You can set the environment via the `FLASK_ENV` environment variable (development, production, testing). See config.py for details.

Alternatively, you can set `APP_SETTINGS` to point to a config class.
