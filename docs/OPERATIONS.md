# Operatività tecnica

Ultimo aggiornamento: 13 luglio 2026.

## Architettura

- Applicazione Flask monolitica in `app.py`.
- Rendering server-side con Jinja2.
- SQLAlchemy ORM; SQLite locale e PostgreSQL in produzione.
- JavaScript vanilla esternalizzato per rispettare la Content Security Policy.
- Flask-Login per l'area admin.
- Flask-Mail per le notifiche.
- Flask-Limiter per i limiti di richiesta.
- Flask-Talisman per gli header di sicurezza.
- APScheduler per i promemoria.
- Google Calendar come collante con Arzamed.

Non introdurre framework frontend, SQL grezzo o dipendenze non necessarie.

## Ambienti

`FLASK_ENV` seleziona `development`, `production` o `testing` da `config.py`.

- Development: SQLite predefinito, debug attivo, cookie utilizzabili su HTTP locale.
- Production: debug disattivato e cookie di sessione `Secure`.
- Testing: database SQLite in memoria, email soppresse, Calendar e Analytics disattivati.

## Variabili d'ambiente

| Variabile | Scopo | Sensibile |
|---|---|---|
| `SECRET_KEY` | Firma della sessione | Sì |
| `FLASK_ENV` | Configurazione applicativa | No |
| `DATABASE_URL` | Connessione PostgreSQL di produzione | Sì |
| `MAIL_SERVER` | Server SMTP | No |
| `MAIL_PORT` | Porta SMTP | No |
| `MAIL_USE_TLS` | Abilitazione TLS SMTP | No |
| `MAIL_USERNAME` | Account mittente | Sì |
| `MAIL_PASSWORD` | Password applicativa SMTP | Sì |
| `MAIL_DEFAULT_SENDER` | Nome/indirizzo mittente | Potenzialmente |
| `GOOGLE_CALENDAR_ICS_URL` | Lettura del calendario condiviso con Arzamed | Sì |
| `CALENDARIO_CACHE_SECONDI` | Durata cache calendario, default 300 | No |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Percorso della credenziale di scrittura | Sì |
| `GOOGLE_CALENDAR_ID` | Calendario su cui scrivere | Sì |
| `GOOGLE_ANALYTICS_ID` | ID GA4 | No |

Le credenziali restano in `.env` o nel secret manager dell'hosting. Il JSON dell'account di servizio non va committato.

## Modelli principali

- `Admin`: utente dell'area riservata.
- `Appuntamento`: prenotazione sanitaria e relativo stato.
- `Corso`: singola data di corso/laboratorio.
- `PersonaCorso`: rubrica dei partecipanti e delle famiglie.
- `IscrizioneCorso`: richiesta collegata, quando possibile, a corso e persona.
- `PercorsoAccompagnamento`: edizione del corso nascita completo.
- `IncontroAccompagnamento`: incontro di una specifica edizione.
- `PresenzaAccompagnamento`: registro presenze.
- `RegistroEvento`: log di email, sincronizzazioni ed errori parziali.

Le regole di prodotto e i conteggi posti sono descritti in `SITE_MAP_AND_FLOWS.md`.

## Stati

- Appuntamenti: `In attesa`, `Confermato`, `Annullato`.
- Iscrizioni corso: `Nuova`, `Contattato`, `Confermato`, `Annullato`.
- Corsi: `Aperto`, `Completo`, `Chiuso`, `Annullato`, `Concluso`.
- Percorsi nascita: `Bozza`, `Aperto`, `Chiuso`, `Concluso`.

Lo stato `Da ricontattare` è previsto dalla roadmap quando serve distinguere richieste senza data, ma va aggiunto soltanto verificando modello, interfaccia, email e test.

## Google Calendar e Arzamed

- Lettura: `GOOGLE_CALENDAR_ICS_URL` permette di conoscere impegni e chiusure segnati sul calendario sincronizzato da Arzamed.
- Cache: controllata da `CALENDARIO_CACHE_SECONDI`.
- Scrittura: un account di servizio crea o aggiorna eventi quando appuntamenti o corsi vengono confermati.
- L'account di servizio deve avere sul calendario soltanto i permessi necessari.
- Un conflitto con un evento Calendar deve generare un alert, non impedire in assoluto l'inserimento admin.

## Errori parziali

Il dato principale ha priorità:

- una prenotazione non deve andare persa se l'email fallisce;
- un'iscrizione non deve andare persa se Calendar fallisce;
- un corso non deve scomparire per un errore di sincronizzazione.

Dopo il salvataggio, gli errori secondari devono essere registrati in `RegistroEvento`. Quando l'errore riguarda un'azione admin, mostrare un avviso comprensibile senza fingere che l'intera operazione sia fallita.

## Sicurezza

- CSRF manuale tramite `_csrf_token` di sessione; verificare ogni nuovo form che modifica dati.
- Rate limiting almeno su prenotazione e login.
- Cookie sicuri in produzione.
- Nessun segreto hardcoded.
- Nessun dato personale nei log oltre ciò che è realmente necessario.
- Confermare che la CSP autorizzi soltanto origini indispensabili.
- Proteggere route private e admin con autenticazione e controllo degli identificativi.

### Credenziale admin iniziale

Su database vuoto `app.py` crea attualmente `admin` con password prevedibile. È accettabile solo in locale e deve essere rimosso, sostituito con configurazione sicura o reso obbligatorio al primo avvio prima della produzione.

## Database e migrazioni

Per database SQLite legacy, eseguire una sola volta e nell'ordine:

```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
```

Non eseguire migrazioni una tantum alla cieca su dati reali. Fare prima un backup e verificare lo schema.

Per PostgreSQL utilizzare Flask-Migrate/Alembic e revisionare manualmente la migrazione generata. `db.create_all()` può creare un database nuovo ma non sostituisce le migrazioni evolutive.

## Comandi locali

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 -m flask --app app run
pytest
git diff --check
```

Aggiornare `requirements.txt` solo quando cambia realmente una dipendenza e controllare le differenze prodotte.

## Checklist di deploy

- Stato Git pulito e commit identificabile.
- Tutti i test superati.
- Migrazioni provate su una copia dei dati.
- Backup e procedura di ripristino verificati.
- `FLASK_ENV=production`, `SECRET_KEY` stabile e segreti configurati.
- Credenziale admin predefinita rimossa o sostituita.
- HTTPS e cookie sicuri verificati.
- Email reali testate con mittente corretto.
- Lettura e scrittura Calendar testate con permessi minimi.
- GA4 caricato solo dopo consenso.
- Privacy, cookie e policy operative validate.
- Log controllati e privi di dati personali superflui.
- Nome del logo normalizzato: Git registra attualmente `static/img/logo.PNG`, mentre i template richiamano `static/img/logo.png`; uniformare prima di un deploy su filesystem case-sensitive.
- Controllo visivo desktop/mobile completato.

## Dati esclusi dalla documentazione

Non aggiungere a `docs/`:

- contenuto di `.env`;
- database o backup reali;
- JSON degli account di servizio;
- URL iCal;
- elenchi iscritti, pazienti o partecipanti;
- feedback non anonimizzati o prove di consenso.
