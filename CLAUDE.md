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

## Linee guida design e UX
- Il sito deve comunicare fiducia sanitaria, calore familiare e professionalità. Il tono visivo deve essere accogliente per neogenitori, famiglie e aziende, senza perdere autorevolezza clinica.
- Ogni sezione deve avere uno scopo chiaro: informare, rassicurare, guidare alla prenotazione sanitaria, all'iscrizione a un corso o al contatto diretto.
- Evitare sezioni ridondanti, CTA duplicate o percorsi che confondono l'utente. Una schermata deve avere una priorità visiva chiara.
- Mantenere separati i flussi: prenotazione prestazioni sanitarie, iscrizione individuale ai corsi, richiesta diretta per corsi aziendali o di gruppo.
- Le consulenze e le iscrizioni ai corsi sono fondamentali: non trattarle come contenuti secondari rispetto alle prestazioni sanitarie.
- Usare un sistema visivo coerente: stessa palette, stessi font, stessi stili di card, icone, bottoni, form e tabelle.
- Prima di introdurre nuovi colori, spaziature, ombre o componenti, verificare se esiste già uno stile equivalente in `static/css/stile.css`.
- Evitare estetiche generiche da template AI: gradienti gratuiti, emoji decorative, icone incoerenti, card troppo simili tra loro, testi riempitivi.
- Preferire immagini reali o `static/img/placeholder.png` quando manca ancora il materiale definitivo. Non creare illustrazioni casuali se non sono coerenti con il brand. Prima del push finale verranno fornite altre foto tra cui scegliere; fino ad allora mantenere la foto principale di Selene come elemento personale e riconoscibile.
- I testi devono essere concreti, rassicuranti e orientati al valore per l'utente. Evitare frasi vaghe come "servizi su misura" se non spiegano cosa ottiene la persona.
- CTA brevi e specifiche: es. "Prenota", "Iscrizione individuale", "Richiedi il corso in studio o in azienda".
- "Scrivimi" e WhatsApp devono essere riservati soprattutto ad aziende/gruppi e a chi non trova una data adatta; non usarli come CTA generica quando esiste un flusso più specifico.
- Accessibilità sempre da verificare: contrasto leggibile, focus visibile, label nei form, pulsanti facilmente cliccabili anche da mobile.
- Ogni modifica estetica importante deve essere controllata su desktop e mobile prima di considerarla conclusa.

## Proof of value e conversione
- Ogni pagina orientata alla conversione deve chiarire rapidamente: per chi è, cosa ottiene l'utente, cosa impara o risolve, durata/formato, cosa succede dopo l'invio e quale azione compiere.
- Per corsi e consulenze, evitare promesse generiche di serenità. Preferire dettagli pratici: gesti allenati, segnali da osservare, routine, materiali utili, confini clinici, date disponibili e gestione delle liste di interesse.
- Ispirarsi ai siti efficaci del settore per struttura e chiarezza, non per copiarne lo stile: esempi utili sono pagine che mostrano "cosa imparerai", credenziali del professionista, formato del corso, posti/date, FAQ e prossima azione.
- La promessa da far percepire entro pochi secondi è: "Qui c'è una professionista sanitaria che parla anche ai genitori in modo umano" e "Qui posso imparare cose pratiche per proteggere mio figlio".
- I testi possono essere modificati liberamente quando migliorano chiarezza, fiducia, proof of value o conversione, mantenendo tono sanitario, umano e non sensazionalistico.

## Posizionamento commerciale
- Il progetto non è solo un sito vetrina: deve sostenere tre aree di business con pari dignità.
- Prestazioni infermieristiche.
- Corsi in presenza: BLSD, disostruzione pediatrica e tagli sicuri, corso di accompagnamento alla nascita, laboratori per l'infanzia.
- Consulenze per neogenitori sulla gestione del neonato, del sonno e dei primi mesi.
- Le modifiche grafiche e testuali devono mantenere equilibrio tra queste aree, senza spingere eccessivamente un solo servizio salvo richiesta esplicita.
- Il ruolo percepito del sito deve avvicinarsi a "guida per famiglie", senza perdere la credibilità di studio infermieristico.
- Pubblico prioritario per i contenuti famiglia: neomamma stanca, genitori, partner, nonni e caregiver che cercano indicazioni pratiche e rassicuranti.
- Le consulenze verranno lanciate insieme al sito e saranno sostenute da una campagna social dedicata; costruire le pagine in modo che siano pronte a ricevere quel traffico.

## Flussi operativi da mantenere separati
- Prestazioni sanitarie: prenotazione online tramite `/prenota`, con date e orari disponibili.
- Corsi individuali: iscrizione tramite `/iscrizione-corsi`, collegata alle date corso create in admin.
- Nessuna data corso disponibile: raccogliere l'interesse e salvare la richiesta in admin come contatto da ricontattare.
- Aziende e gruppi: contatto diretto, soprattutto per BLSD in studio o in azienda; non far prenotare direttamente un'azienda dal form individuale.
- Consulenze neogenitori: flusso dedicato e separato dalla prenotazione sanitaria; in fase iniziale può essere contatto diretto, poi potrà diventare prenotazione dedicata.
- Pagamenti online: possibile evoluzione futura, da implementare solo quando flussi, stati admin, email e calendario saranno stabili.

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
- `GOOGLE_SERVICE_ACCOUNT_FILE` — percorso al file JSON della chiave dell'account di servizio Google (per SCRIVERE eventi su Calendar quando un appuntamento viene confermato). File sensibile: non va mai committato (già escluso da `.gitignore`).
- `GOOGLE_CALENDAR_ID` — ID del calendario Google su cui creare gli eventi (Impostazioni calendario → Integra calendario → "ID calendario"). L'account di servizio deve avere accesso "Apportare modifiche agli eventi" su questo calendario.
- `GOOGLE_ANALYTICS_ID` — ID misurazione GA4 (formato `G-XXXXXXXXXX`). Se impostato, il sito mostra il banner cookie e carica Google Analytics solo dopo consenso dell'utente.

## Migrazione database

Se aggiorni un database `appuntamenti.db` già esistente (con dati reali), dopo aver aggiornato il codice esegui una volta sola:
```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
```
Aggiungono le colonne necessarie per collegare appuntamenti e corsi agli eventi Google Calendar corrispondenti; per i corsi aggiungono anche `tipo` e `durata_ore`. Non serve se il database viene creato da zero (lo schema aggiornato include già queste colonne).

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
