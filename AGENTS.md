# Studio Infermieristico

## Stack tecnologico
- Python 3.14 + Flask
- SQLAlchemy (ORM) + SQLite locale, configurazione pronta per PostgreSQL tramite `DATABASE_URL`
- Flask-Login, Flask-Mail, Flask-Limiter, Flask-Talisman
- APScheduler (promemoria 24h)
- Jinja2 + HTML/CSS/JavaScript vanilla

## Contesto strategico e obiettivi 2026
- L'attività è operativa da gennaio 2026 a Montesilvano/Pescara. I corsi e le attività per l'infanzia hanno un bacino locale/provinciale; la consulenza del sonno deve poter raggiungere famiglie in tutta Italia.
- Il lancio grafico del sito è previsto idealmente per l'inizio di settembre 2026, ma non è una scadenza pubblica o rigida. Al lancio il sito deve apparire completo e coerente anche se alcuni automatismi rimandano temporaneamente al contatto diretto.
- Il sito è il progetto centrale da cui dipendono lancio delle consulenze online, crescita social e campagne future. Deve essere una vetrina autorevole con un retrobottega gestionale leggero, non un marketplace impersonale.
- L'obiettivo commerciale prioritario non è massimizzare il numero di clienti, ma aumentare valore percepito, qualità dei contatti e scontrino medio, mantenendo un work/life balance sostenibile.
- Lo sviluppo deve essere controllato e a basso rischio: evitare investimenti, dipendenze o automazioni premature finché offerta, flussi e domanda non sono validati.
- Obiettivo economico indicativo: arrivare progressivamente a 1.500-2.000 euro mensili netti dopo costi, contributi e imposte; non sacrificare chiarezza, qualità o sostenibilità personale per inseguire volume.
- Corsi in presenza e laboratori hanno già domanda reale. La consulenza del sonno ha ricevuto richieste ma resta un servizio da validare prima del lancio nazionale.

## Regole del progetto
- No framework frontend.
- Mantenere il rendering server-side con Jinja2.
- Utilizzare SQLAlchemy ORM (no SQL grezzo).
- Mantenere il codice applicativo PostgreSQL-ready: evitare assunzioni legate solo a SQLite fuori dagli script di migrazione una tantum.
- Evitare dipendenze non necessarie.
- Privilegiare codice semplice e leggibile.
- Variabili sensibili (SECRET_KEY, MAIL_PASSWORD) sempre in `.env`, mai hardcoded.
- Codice Python in inglese; interfaccia utente in italiano.
- Commenti solo se realmente utili.
- Preferire funzioni piccole e riutilizzabili.

## Linee guida design e UX
- Il sito deve comunicare fiducia sanitaria, calore familiare e professionalità. Il tono visivo deve essere accogliente per neogenitori, famiglie e aziende, senza perdere autorevolezza clinica.
- S.C. Studio Infermieristico è la sede; per famiglie e neogenitori il riferimento umano è Selene. Nei testi rivolti ai genitori, far emergere Selene come professionista competente e vicina, non come brand impersonale.
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
- "Scrivimi" e WhatsApp devono essere riservati soprattutto alla call sonno nella fase pilota, ad aziende/gruppi e a chi non trova una data adatta; non usarli come CTA generica quando esiste un flusso più specifico.
- Accessibilità sempre da verificare: contrasto leggibile, focus visibile, label nei form, pulsanti facilmente cliccabili anche da mobile.
- Ogni modifica estetica importante deve essere controllata su desktop e mobile prima di considerarla conclusa.

## Identità visiva definitiva
- Il riferimento cromatico principale è il verde salvia reale dello studio, campionato in `#B1BBA5`. Non sostituirlo con verdi smeraldo, bosco o sanitari più freddi come colore dominante.
- Palette ufficiale e ruoli:
  - salvia identitario `#B1BBA5`: header, menu mobile, grandi fasce e superfici di brand;
  - salvia chiarissimo `#E5E9E0`: fondi informativi e alternanza leggera;
  - carta `#F7F5F1`: fondo principale delle pagine;
  - verde azione `#506A59`: pulsanti primari e piccoli pannelli funzionali con testo bianco;
  - verde testo `#304438`: titoli, navigazione e testo sui fondi salvia;
  - verde profondo `#3F5948`: hover e footer, da non estendere a grandi porzioni della pagina;
  - rosso cuore `#9A4E56`: firma, linea continua, bordi o micro-etichette; non usarlo come colore diffuso.
- Su `#B1BBA5` usare testo `#304438`, mai testo bianco: il contrasto del bianco sul salvia è insufficiente. Il bianco può essere usato su `#506A59` o `#3F5948`.
- I token cromatici definitivi sono dichiarati in `:root` dentro `static/css/stile.css`. Prima di aggiungere un codice colore verificare se esiste già il token corrispondente.
- Header: fondo salvia, logo e navigazione verde scuro. Footer: verde profondo con testo chiaro. Le grandi sezioni commerciali devono preferire il salvia al verde scuro.
- Tipografia ufficiale: `Bricolage Grotesque` per titoli brevi e gerarchia commerciale; `Atkinson Hyperlegible` per testi, moduli, tabelle e contenuti informativi.
- La firma visiva è una linea rossa sottile ispirata al cuore anatomico/uncinetto. Deve guidare una sequenza o sottolineare un passaggio reale, non diventare una decorazione ripetuta senza funzione.
- Le fotografie professionali e reali di Selene, dello studio, dei corsi e dei manufatti all'uncinetto sono il principale elemento distintivo. Non coprirle con gradienti pesanti e non sostituirle con stock generici.
- Evitare motivi botanici generici, palette maternità rosa/crema standard, verdi ospedalieri saturi, grandi fondi scuri, pillole decorative e card tutte identiche.
- La comunicazione social, le landing e i PDF commerciali devono usare la stessa palette, le stesse fotografie e la stessa gerarchia del sito.

## Proof of value e conversione
- Ogni pagina orientata alla conversione deve chiarire rapidamente: per chi è, cosa ottiene l'utente, cosa impara o risolve, durata/formato, cosa succede dopo l'invio e quale azione compiere.
- Per corsi e consulenze, evitare promesse generiche di serenità. Preferire dettagli pratici: gesti allenati, segnali da osservare, routine, materiali utili, confini clinici, date disponibili e gestione delle liste di interesse.
- Ispirarsi ai siti efficaci del settore per struttura e chiarezza, non per copiarne lo stile: esempi utili sono pagine che mostrano "cosa imparerai", credenziali del professionista, formato del corso, posti/date, FAQ e prossima azione.
- La promessa da far percepire entro pochi secondi è: "Qui c'è una professionista sanitaria che sa cosa fa, parla ai genitori in modo umano e può essere la scelta giusta per la mia famiglia".
- I testi possono essere modificati liberamente quando migliorano chiarezza, fiducia, proof of value o conversione, mantenendo tono sanitario, umano e non sensazionalistico.
- Non promettere mai risultati garantiti, soluzioni magiche o "bacchette magiche". Comunicare metodo, esperienza e supporto concreto, non certezza assoluta dell'esito.

## Posizionamento commerciale
- Il progetto resta principalmente una vetrina autorevole dell'attività, con un retrobottega gestionale leggero. Deve sostenere la crescita commerciale dello studio con due pilastri visibili: corsi in presenza e consulenza del sonno. I corsi restano il servizio già validato; la consulenza del sonno è il secondo servizio da validare e lanciare a livello nazionale. Le prestazioni infermieristiche restano presenti e prenotabili, ma non devono dominare header, homepage o messaggio principale salvo richiesta esplicita.
- Corsi in presenza: BLSD, disostruzione pediatrica e tagli sicuri, corso di accompagnamento alla nascita, laboratori per l'infanzia.
- Laboratori per l'infanzia: soprattutto laboratori alimentari di supporto allo svezzamento e laboratori di gioco e sviluppo.
- Consulenze per neogenitori: al lancio la pagina commerciale deve concentrarsi verticalmente sulla gestione del sonno infantile 0-12 mesi. Spannolinamento, ciuccio e altri passaggi pratici restano possibili evoluzioni future e non devono essere mescolati nella landing sonno.
- Prestazioni infermieristiche: flusso sanitario separato, chiaro e accessibile, ma con priorità visiva secondaria rispetto ai nuovi servizi da lanciare.
- Le modifiche grafiche e testuali devono mantenere equilibrio tra corsi e consulenza del sonno, evitando che le prestazioni sanitarie tornino a dominare la homepage o che la consulenza oscuri i corsi già validati.
- Il ruolo percepito del sito deve avvicinarsi a "guida per genitori nei primi mesi", senza perdere la credibilità di studio infermieristico.
- Pubblico prioritario per i contenuti famiglia: neomamma stanca e genitori preoccupati. Pubblici attivi: coppie alla prima gravidanza, partner, nonni e caregiver. Le aziende sono un target secondario da gestire quando arriva la richiesta, non il centro della comunicazione.
- Le consulenze online possono rivolgersi a famiglie in tutta Italia e verranno lanciate insieme al sito con campagna social dedicata; costruire le pagine in modo che siano pronte a ricevere traffico freddo.
- L'obiettivo di conversione iniziale è generare contatti qualificati, non vendite immediate o iscrizioni forzate.

## Gerarchia commerciale delle pagine principali
- La homepage non deve tornare a essere un catalogo. Nel hero mostrare una sola promessa, Selene e al massimo due azioni: `Scopri i corsi` e `Richiedi la call gratuita`.
- Struttura commerciale della homepage da mantenere salvo richiesta esplicita: hero; prova di fiducia; due pilastri corsi/sonno; prossime date; corso di accompagnamento alla nascita; metodo di Selene; testimonianze; prestazioni infermieristiche in fascia secondaria; CTA finale.
- Non ripetere gli stessi percorsi nel hero e subito dopo. Ogni blocco deve aggiungere una nuova informazione o prova di valore.
- Le prestazioni infermieristiche devono rimanere in navigazione e avere un flusso chiaro, ma non essere il bottone dominante dell'header o della homepage.
- La pagina `/consulenze-online` è una landing verticale sulla consulenza del sonno infantile 0-12 mesi, pronta per traffico freddo nazionale. Non trasformarla nuovamente in una pagina generica con sonno, ciuccio, spannolinamento e routine insieme.
- La landing sonno deve chiarire: problemi osservabili, differenze indicative tra 0-4 e 5-12 mesi, metodo, due formule di servizio, confini clinici, FAQ e call conoscitiva gratuita.
- Le due formule della consulenza sonno hanno ruoli diversi: `Consulenza mirata` per una singola difficoltà circoscritta e `Percorso sonno personalizzato` come offerta principale quando più aspetti si influenzano tra loro. La formula breve non deve svalutare il percorso principale.
- Il prezzo non è la leva principale del sito. Nei materiali inviati a famiglie già interessate, i riferimenti attuali sono 75 euro per la consulenza mirata e 180 euro per il percorso principale; sul sito privilegiare valore, appropriatezza e call gratuita salvo richiesta esplicita.
- La call conoscitiva dura indicativamente 15 minuti, precede l'eventuale pagamento e serve anche a evitare di proporre un servizio non adatto.
- La consulenza non formula diagnosi, non prescrive terapie, non sostituisce il pediatra e non promette risultati garantiti. Rendere questi confini visibili senza usare un tono difensivo o allarmistico.
- Le testimonianze del corso di accompagnamento alla nascita possono essere pubblicate in forma anonima quando autorizzate. Usare soltanto feedback reali, senza riscriverli in modo da alterarne il significato.

## Naming e messaggi
- Evitare un tono emergenziale per le consulenze ai neogenitori: `SOS neomamma` è troppo urgente come nome principale. Per il lancio usare `Consulenza sonno` o `Consulenza del sonno` in navigazione e pagina. `Consulenze genitori` può diventare in futuro il contenitore di più servizi, ma non deve rendere generica la landing attuale.
- Mantenere nei testi parole chiave SEO pertinenti come sonno infantile, sonno 0-12 mesi, consulenza del sonno, primi mesi e consulenza neogenitori; non inserire ciuccio o spannolinamento nella pagina sonno solo per ampliare artificialmente le keyword.
- `Corso di accompagnamento alla nascita` resta il nome ufficiale.
- `Disostruzione pediatrica e tagli sicuri` resta il nome ufficiale, anche se lungo, perché è chiaro e specifico.
- BLSD va comunicato come investimento concreto nella sicurezza degli ambienti, non solo come corso tecnico.
- Il corso di accompagnamento alla nascita deve valorizzare la presenza di 5 professionisti sanitari: infermiera, ostetrica, psicologa, osteopata e nutrizionista. La differenza rispetto a percorsi generici è la visione a 360 gradi sulla gravidanza e sul rientro a casa.
- Usare foto personali e reali di Selene/studio quando disponibili; rafforzano fiducia e riconoscibilità più di immagini neutre.

## Dati operativi e commerciali attuali
- Questi dati servono come contesto interno: non mostrarli automaticamente in pagina e non modificarli senza richiesta.
- BLSD: 60-75 euro a persona, normalmente una volta al mese, classe standard fino a 10 persone. Con 14 partecipanti servono due istruttori; quando interviene un collaboratore il margine viene ripartito secondo gli accordi reali, non stimato dal sito.
- Disostruzione pediatrica e tagli sicuri: 35 euro a persona o 60 euro a coppia, normalmente una volta al mese, circa 6-8 partecipanti e massimo indicativo 10.
- Laboratori alimentari/gioco: circa quattro appuntamenti al mese, 20-25 euro a bambino, gruppi abituali di 4-6 bambini.
- Corso di accompagnamento alla nascita: 225 euro a coppia, 9 incontri, mediamente 5 coppie e capienza indicativa 7-8 coppie. Una coppia conta come un posto nel percorso completo.
- Nel percorso nascita i compensi degli altri professionisti vengono fatturati direttamente da loro secondo gli accordi esistenti. Non rappresentare l'intero prezzo come ricavo di Selene.
- Prestazioni infermieristiche: frequenze e importi variabili; costituiscono un flusso separato e non vanno usate come offerta civetta per i servizi famiglia.
- Principali costi fissi noti: 700 euro mensili di affitto e circa 500 euro tra utenze, software, commercialista e materiali; contributi e imposte sono esclusi da questa stima.

## Flussi operativi da mantenere separati
- Prestazioni sanitarie: prenotazione online tramite `/prenota`, con date e orari disponibili.
- Corsi individuali: iscrizione tramite `/iscrizione-corsi`, collegata alle date corso create in admin.
- Nessuna data corso disponibile: raccogliere l'interesse e salvare la richiesta in admin come contatto da ricontattare.
- Aziende e gruppi: contatto diretto, soprattutto per BLSD in studio o in azienda; non far prenotare direttamente un'azienda dal form individuale.
- Consulenza del sonno: flusso dedicato e separato dalla prenotazione sanitaria; in fase iniziale può terminare con contatto diretto via WhatsApp/telefono, poi potrà diventare una prenotazione dedicata.
- Consulenza del sonno: prevedere call conoscitiva gratuita come leva forte anche in homepage. Il pagamento, quando verrà introdotto, dovrà avvenire dopo la prima call gratuita.
- Prezzi: per ora non mostrarli come leva principale; orientare a contatto/informazioni, soprattutto per consulenze e percorsi.
- WhatsApp può essere usato per la call sonno nella fase pilota, per genitori indecisi, aziende/gruppi e per chi non trova una data adatta. Evitare però che diventi un widget indistinto su ogni pagina o sostituisca un flusso più specifico quando il modulo è la scelta migliore.
- Se l'utente non sa cosa scegliere, la soluzione ideale futura è un quiz/percorso guidato tipo "Da dove parto?", più utile di una semplice lista di link.
- Pagamenti online: possibile evoluzione futura, da implementare solo quando flussi, stati admin, email e calendario saranno stabili.

## Roadmap gestionale commerciale
- Il sito deve evolvere verso un piccolo gestionale commerciale dello studio: non solo moduli, ma controllo di prenotazioni, corsi, consulenze, aziende, ricontatti e calendario.
- Prestazioni sanitarie: conferma sempre manuale. Prima della produzione verrà fornito l'elenco delle durate slot da allineare al gestionale sanitario.
- Appuntamenti a domicilio: non devono essere prenotati direttamente online; vanno gestiti con contatto diretto come i corsi aziendali, perché richiedono valutazione di spostamento, zona e fattibilità.
- Stati appuntamento: mantenere quelli esistenti e aggiungere solo `Da ricontattare` quando serve distinguere una richiesta non ancora gestibile con data/orario.
- Modifica/annullamento appuntamento da email: il paziente deve avere un link per modificare o annullare. Consentire fino a 24 ore prima se l'appuntamento cade da martedì a sabato; se cade di lunedì, consentire entro il sabato precedente alle 12:00. Dopo modifica, lo stato torna `In attesa` e va inviata una notifica a `sc.studioinfermieristico@gmail.com`.
- Corsi: l'iscrizione online è una richiesta finché non sarà implementato il pagamento anticipato. La capienza massima verrà fornita corso per corso; le iscrizioni di coppia valgono come 2 posti.
- Corso di accompagnamento alla nascita: il flusso ha due livelli. Le date pubbliche sono open day gratuiti conoscitivi con iscrizione tramite modulo sul sito. Il corso completo usa invece un modulo di iscrizione accessibile solo tramite link privato generico, non presente in navigazione e non indicizzato. Se il link viene inoltrato, l'iscrizione viene comunque accettata. L'invio del modulo privato vale come iscrizione effettiva e va salvato come `Confermato`.
- Open day accompagnamento alla nascita: è sempre previsto e serve in entrambe le direzioni, per far conoscere i professionisti alle famiglie e per conoscere le famiglie prima del percorso completo.
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

## Campagne e landing future
- Per campagne social o advertising, valutare pagine verticali separate quando il traffico è molto specifico: una landing per consulenze primi mesi, una per disostruzione/tagli sicuri, una per open day nascita. Una landing non sostituisce la pagina principale del servizio: serve a far atterrare un pubblico con un bisogno preciso su un messaggio più diretto.
- Prima di creare landing separate, chiarire obiettivo, target, CTA e fonte traffico della campagna.

## SEO, autorevolezza sanitaria e misurazione
- Ogni pagina pubblica deve avere un solo `h1` descrittivo; usare `h2` e `h3` in ordine gerarchico, non per dimensionare visivamente il testo.
- Mantenere meta description specifica, canonical, Open Graph e immagine social coerente. Le pagine commerciali principali devono essere condivisibili senza titolo o descrizione generici.
- Rendere evidenti autore, ruolo di Selene, iscrizione all'Albo OPI di Pescara, contatti e sede. Per contenuti sanitari indicare fonti affidabili quando si fanno affermazioni cliniche o di sicurezza.
- Mantenere i dati strutturati `MedicalBusiness` per lo studio e `Service` per la consulenza del sonno; aggiornarli se cambiano URL, offerta o dati pubblici.
- Le CTA commerciali principali devono avere un attributo `data-conversion` coerente. Il file `static/js/conversion-tracking.js` invia eventi solo quando GA4 è disponibile e non deve aggirare il consenso cookie.
- Distinguere almeno le conversioni di corsi, call gratuita, prestazioni e contatto aziende. Non attribuire tutti i clic a un generico evento WhatsApp.
- Prima di una campagna verificare che landing, evento di conversione, messaggio WhatsApp/modulo e risposta successiva siano coerenti tra loro.

## Checklist prima di considerare conclusa una modifica pubblica
- Verificare che la modifica rispetti la gerarchia corsi/consulenza sonno/prestazioni e non introduca una CTA concorrente senza motivo.
- Controllare homepage e pagina interessata almeno a 1440 px e 390 px; verificare menu, sticky CTA, immagini, footer e assenza di scorrimento orizzontale.
- Controllare contrasto di testo, focus da tastiera, label, dimensione dei target touch e significato dei link.
- Verificare che non siano stati introdotti colori fuori palette, font aggiuntivi, gradienti gratuiti, stock generici o componenti duplicati.
- Controllare un solo `h1`, metadati corretti e dati strutturati validi quando la modifica riguarda una pagina commerciale.
- Eseguire `pytest` e `git diff --check`. Non considerare conclusa una modifica estetica importante basandosi soltanto sul codice senza controllo visivo.


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
- `DATABASE_URL` — URL del database di produzione. Se non impostato, il sito usa SQLite locale (`appuntamenti.db`). Gli URL `postgres://...`/`postgresql://...` vengono normalizzati per usare `psycopg`.

## Migrazione database

Se aggiorni un database `appuntamenti.db` già esistente (con dati reali), dopo aver aggiornato il codice esegui una volta sola:
```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
```
Aggiungono le colonne necessarie per collegare appuntamenti e corsi agli eventi Google Calendar corrispondenti; per i corsi aggiungono anche `tipo`, `durata_ore`, stato/capienza, collegamento tra iscrizioni e singole date corso, rubrica famiglie/partecipanti, collegamento tra iscrizioni e persona salvata, tabelle del modulo privato per il percorso di accompagnamento alla nascita e registro eventi. Non serve se il database viene creato da zero (lo schema aggiornato include già queste colonne/tabelle).

Il progetto è predisposto per Flask-Migrate/Alembic. Prima del deploy su PostgreSQL, generare e verificare migrazioni reali invece di affidarsi a `db.create_all()` per evolvere database con dati reali.

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
- `RegistroEvento` — log operativo consultabile in admin per errori parziali, email e sincronizzazioni Google Calendar
- Admin default: `admin` / `cambiami123` (creato da `app.py` se il DB è vuoto)

## Sicurezza
- CSRF gestito manualmente via `_csrf_token` di sessione (`generate_csrf_token`), validato in `prenota` e `login`.
- Rate limiting su `prenota` e `login` (`Flask-Limiter`).
- Header di sicurezza via `Flask-Talisman`; cookie di sessione sicuri in produzione.

## Errori parziali
- Il salvataggio del dato principale ha priorità: prenotazioni, iscrizioni e corsi non devono andare persi se email o Google Calendar falliscono.
- Se email o Google Calendar falliscono, registrare l'errore in `RegistroEvento` e mostrare un avviso admin quando l'azione riguarda la sincronizzazione Calendar.
- Google Calendar resta un collante con Arzamed, ma gli eventi creati/modificati dal sito devono essere precisi e tracciabili per evitare discrepanze.
