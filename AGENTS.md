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
- Il progetto non è solo un sito vetrina: deve sostenere la crescita commerciale dello studio, con focus prioritario su corsi in presenza e consulenze online per neogenitori. Le prestazioni infermieristiche restano presenti e prenotabili, ma non devono dominare header, homepage o messaggio principale salvo richiesta esplicita.
- Corsi in presenza: BLSD, disostruzione pediatrica e tagli sicuri, corso di accompagnamento alla nascita, laboratori per l'infanzia.
- Consulenze per neogenitori sulla gestione del neonato, del sonno e dei primi mesi.
- Prestazioni infermieristiche: flusso sanitario separato, chiaro e accessibile, ma con priorità visiva secondaria rispetto ai nuovi servizi da lanciare.
- Le modifiche grafiche e testuali devono mantenere equilibrio tra corsi e consulenze, senza spingere eccessivamente un solo servizio salvo richiesta esplicita.
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

## Roadmap gestionale commerciale
- Il sito deve evolvere verso un piccolo gestionale commerciale dello studio: non solo moduli, ma controllo di prenotazioni, corsi, consulenze, aziende, ricontatti e calendario.
- Prestazioni sanitarie: conferma sempre manuale. Prima della produzione verrà fornito l'elenco delle durate slot da allineare al gestionale sanitario.
- Appuntamenti a domicilio: non devono essere prenotati direttamente online; vanno gestiti con contatto diretto come i corsi aziendali, perché richiedono valutazione di spostamento, zona e fattibilità.
- Stati appuntamento: mantenere quelli esistenti e aggiungere solo `Da ricontattare` quando serve distinguere una richiesta non ancora gestibile con data/orario.
- Modifica/annullamento appuntamento da email: il paziente deve avere un link per modificare o annullare. Consentire fino a 24 ore prima se l'appuntamento cade da martedì a sabato; se cade di lunedì, consentire entro il sabato precedente alle 12:00. Dopo modifica, lo stato torna `In attesa` e va inviata una notifica a `sc.studioinfermieristico@gmail.com`.
- Corsi: l'iscrizione online è una richiesta finché non sarà implementato il pagamento anticipato. La capienza massima verrà fornita corso per corso; le iscrizioni di coppia valgono come 2 posti.
- Corso di accompagnamento alla nascita: il flusso ha due livelli. Le date pubbliche sono open day gratuiti conoscitivi con iscrizione tramite modulo sul sito. Il corso completo usa invece un modulo di iscrizione accessibile solo tramite link privato generico, non presente in navigazione e non indicizzato. Se il link viene inoltrato, l'iscrizione viene comunque accettata. L'invio del modulo privato vale come iscrizione effettiva e va salvato come `Confermato`.
- Percorso accompagnamento alla nascita: il corso completo è una serie di 9 incontri con vari professionisti. In admin deve essere gestito come edizione/percorso con calendario incontri, iscritti confermati, registro presenze ed export PDF. Una coppia conta come 1 posto. Nel modulo privato raccogliere solo i dati necessari, inclusa la data presunta del parto; non raccogliere altri dati sanitari se non richiesti esplicitamente.
- Corso pieno: proporre la data successiva se disponibile; se non esiste una data utile, mostrare un form di ricontatto con preferenze indicative, come mattina/pomeriggio o giorno della settimana.
- Corsi in admin: prevedere stati propri (`Aperto`, `Completo`, `Chiuso`, `Annullato`, `Concluso`), colori distinti per tipologia/stato e filtri pubblici per permettere all'utente di vedere rapidamente solo i corsi cercati.
- Modelli corso: ogni tipologia deve avere un modello standard riutilizzabile, così l'admin può duplicare o creare nuove date senza riscrivere tutto.
- Admin: deve diventare una cabina di regia con viste per `oggi`, `questa settimana`, `questo mese`, sezioni separate per prenotazioni, corsi, iscrizioni, ricontatti, consulenze e aziende.
- Google Calendar: resta il collante tra Arzamed e sito. Arzamed e prenotazioni online devono lavorare insieme per alleggerire la segreteria. Quando l'admin inserisce corsi o prenotazioni in giorni/orari occupati da note o eventi Google, il sito deve mostrare un alert di conferma ma permettere comunque l'inserimento.
- Corsi modificati: quando un corso con iscritti viene modificato, chiedere se inviare una email automatica agli utenti con la descrizione della modifica.
- Esportazioni: prevedere esportazione PDF degli iscritti/partecipanti corso.
- Pagamenti futuri: pagamento online solo per consulenze online e alcuni corsi, con possibilità di rateizzazione. Non introdurre pagamenti prima di avere policy, stati, email, capienze e calendario stabili.
- Policy: preparare una bozza per cancellazioni, spostamenti, rimborsi, rate e assenze; va validata prima della produzione e con attenzione legale/fiscale.


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
python3 migrazione_gestione_iscritti_corsi.py
```
Aggiungono le colonne necessarie per collegare appuntamenti e corsi agli eventi Google Calendar corrispondenti; per i corsi aggiungono anche `tipo`, `durata_ore`, stato/capienza, collegamento tra iscrizioni e singole date corso, rubrica famiglie/partecipanti, collegamento tra iscrizioni e persona salvata e tabelle del modulo privato per il percorso di accompagnamento alla nascita. Non serve se il database viene creato da zero (lo schema aggiornato include già queste colonne).

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
- `Corso` — evento corso/laboratorio mostrato in homepage e gestito in admin
- `PersonaCorso` — rubrica famiglie/partecipanti per corsi e laboratori, con dati genitore/adulto e bambino
- `IscrizioneCorso` — richiesta o iscrizione collegata a un corso e, quando possibile, a una persona in rubrica
- `PercorsoAccompagnamento` — edizione privata del corso di accompagnamento alla nascita
- `IncontroAccompagnamento` — singolo incontro del percorso nascita, con data, professionista e tema
- `PresenzaAccompagnamento` — registro presenze degli iscritti agli incontri del percorso nascita
- Admin default: `admin` / `cambiami123` (creato da `app.py` se il DB è vuoto)

## Sicurezza
- CSRF gestito manualmente via `_csrf_token` di sessione (`generate_csrf_token`), validato in `prenota` e `login`.
- Rate limiting su `prenota` e `login` (`Flask-Limiter`).
- Header di sicurezza via `Flask-Talisman`; cookie di sessione sicuri in produzione.
