# S.C. Studio Infermieristico — Sito Web

Sito web ufficiale di S.C. Studio Infermieristico con sistema di prenotazione appuntamenti, gestione corsi e area admin protetta.

---

## Stack tecnologico

- **Backend:** Python 3.14 + Flask
- **Database:** SQLite + SQLAlchemy
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

MAIL_PASSWORD=app_password_gmail_16_caratteri

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