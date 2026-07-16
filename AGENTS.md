# Studio Infermieristico — istruzioni per gli agenti

## Prima di intervenire

1. Leggere questo file integralmente.
2. Leggere [docs/README.md](docs/README.md) e i documenti pertinenti al compito.
3. Controllare `git status`, `git diff` e gli ultimi commit prima di modificare file.
4. Preservare le modifiche locali e non attribuite: non sovrascriverle, ripristinarle o includerle automaticamente nel proprio lavoro.
5. Fare domande solo quando una risposta può cambiare sostanzialmente il risultato o richiede nuova autorizzazione.

## Fonti di verità

- Questo file: regole operative non negoziabili.
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): attività, pubblici, offerta, obiettivi e dati commerciali interni.
- [docs/BRAND_SYSTEM.md](docs/BRAND_SYSTEM.md): identità visiva e verbale.
- [docs/SITE_MAP_AND_FLOWS.md](docs/SITE_MAP_AND_FLOWS.md): gerarchie, route, CTA e comportamento dei flussi.
- [docs/ROADMAP.md](docs/ROADMAP.md): priorità e stato del progetto.
- [docs/DECISIONS.md](docs/DECISIONS.md): scelte approvate e relative motivazioni.
- [docs/CONTENT_AND_ASSETS.md](docs/CONTENT_AND_ASSETS.md): testi, fotografie e materiali.
- [docs/locandine.md](docs/locandine.md): istruzioni per locandine, PDF e materiali social.
- [docs/OPERATIONS.md](docs/OPERATIONS.md): ambienti, integrazioni, migrazioni e deploy.
- [README.md](README.md): installazione e comandi tecnici essenziali.

In caso di contraddizione, questo file prevale sulle altre fonti. Non duplicare una correzione in più documenti: aggiornare la fonte competente e collegarla dalle altre.

## Stack e architettura

- Python 3.14, Flask e Jinja2 con rendering server-side.
- SQLAlchemy ORM; SQLite locale e PostgreSQL tramite `DATABASE_URL`.
- Flask-Login, Flask-Mail, Flask-Limiter, Flask-Talisman e APScheduler.
- HTML, CSS e JavaScript vanilla; nessun framework frontend.
- Mantenere il codice PostgreSQL-ready ed evitare assunzioni SQLite-specific fuori dalle migrazioni una tantum.
- Evitare dipendenze non necessarie, SQL grezzo e architetture premature.
- Codice Python in inglese; interfaccia utente in italiano.
- Preferire funzioni piccole, nomi chiari e commenti soltanto quando spiegano una decisione non evidente.

## Obiettivo e priorità di prodotto

Il sito è una vetrina autorevole con un gestionale commerciale leggero. Deve sostenere una crescita controllata e generare contatti qualificati.

Gerarchia commerciale:

1. corsi in presenza, già validati;
2. consulenza del sonno 0-12 mesi, da validare e lanciare a livello nazionale;
3. prestazioni infermieristiche, sempre accessibili e prenotabili ma visivamente secondarie.

Non trasformare la homepage in un catalogo e non lasciare che un solo servizio oscuri gli altri due livelli. Il lancio grafico è previsto idealmente per l'inizio di settembre 2026, ma non è una scadenza pubblica rigida. Consultare brief e roadmap prima di ampliare l'ambito.

## Design e UX

- Comunicare fiducia sanitaria, calore familiare e professionalità.
- S.C. Studio Infermieristico è la sede; per famiglie e neogenitori il riferimento umano è Selene.
- Usare il sistema definito in `docs/BRAND_SYSTEM.md` e i token presenti in `static/css/tokens.css`.
- Il salvia identitario è `#B1BBA5`; su questo fondo usare testo `#304438`, non bianco.
- Mantenere `Bricolage Grotesque` per i titoli e `Atkinson Hyperlegible` per testi e interfacce.
- Preferire fotografie reali di Selene, dello studio e delle attività. Se manca il materiale usare `static/img/placeholder.png` e registrarlo nell'inventario.
- Per locandine, PDF o materiali social leggere e applicare `docs/locandine.md` prima di creare il contenuto.
- Evitare stock generici, emoji decorative, motivi botanici, icone incoerenti, card tutte uguali e componenti duplicati.
- La linea rossa è una firma funzionale, non una decorazione da ripetere ovunque.
- Ogni schermata deve avere una priorità visiva e ogni sezione uno scopo: informare, rassicurare o guidare all'azione pertinente.
- Prima di creare colori, spaziature, ombre o componenti, verificare se esiste già uno stile equivalente.
- Usare i token alpha di `static/css/tokens.css` per ogni colore semitrasparente; non inserire `rgba()` letterali negli altri moduli CSS.
- Collocare ogni nuova regola nel modulo CSS competente; non creare sezioni `V2`, `V3` o nuovi stili in coda a un file non pertinente.
- Accessibilità obbligatoria: contrasto, focus, label, tastiera, target touch e leggibilità mobile.

## Testi e proof of value

- Usare testi concreti, rassicuranti e orientati a ciò che la persona ottiene, impara, osserva o fa dopo.
- Ogni pagina di conversione deve chiarire: per chi è, cosa offre, formato/durata, cosa succede dopo l'invio e prossima azione.
- Non promettere risultati garantiti, diagnosi, terapie, soluzioni magiche o serenità universale.
- Rendere visibili ruolo di Selene, iscrizione OPI Pescara, metodo e confini clinici.
- Usare i nomi approvati in `BRAND_SYSTEM.md` e `CONTENT_AND_ASSETS.md`.
- La landing `/consulenze-online` resta verticale sulla consulenza del sonno 0-12 mesi. Non reinserire ciuccio, spannolinamento e routine generiche.
- `Consulenza mirata` riguarda una difficoltà circoscritta; `Percorso sonno personalizzato` è l'offerta principale quando più aspetti si influenzano.
- I prezzi non sono la leva principale del sito e i dati economici interni del brief non vanno pubblicati automaticamente.
- Usare soltanto testimonianze reali e autorizzate, senza alterarne il significato.

## Flussi da mantenere separati

- Prestazioni sanitarie: `/prenota`, con richiesta e conferma manuale.
- Corsi individuali: `/iscrizione-corsi`, collegati a date e capienza.
- Nessuna data/corso pieno: proposta della data successiva o richiesta di ricontatto.
- Aziende e gruppi: contatto diretto; non usare il form individuale.
- Appuntamenti a domicilio: contatto e valutazione manuale; non prenotazione diretta.
- Consulenza del sonno: landing e call gratuita dedicate; nella fase pilota può terminare su WhatsApp o telefono.
- Percorso nascita: open day pubblico e modulo completo privato non indicizzato.

WhatsApp è appropriato per call sonno pilota, persone indecise, aziende/gruppi e assenza di date. Non deve sostituire un modulo specifico già disponibile.

Le regole dettagliate su stati, capienza, coppie, modifiche e conferme sono in `docs/SITE_MAP_AND_FLOWS.md`. Non modificarle implicitamente durante un intervento grafico.

## Dati, email e Calendar

- Il salvataggio del dato principale ha priorità su email e sincronizzazioni.
- Se email o Google Calendar falliscono, non perdere prenotazione, iscrizione o corso.
- Registrare gli errori secondari in `RegistroEvento` e mostrare avvisi comprensibili in admin.
- Usare SQLAlchemy ORM e migrazioni esplicite per l'evoluzione dello schema.
- Prima di modificare modelli o stati, verificare route, template, email, Calendar, migrazioni e test coinvolti.
- Google Calendar resta il collante con Arzamed; gli eventi creati dal sito devono essere precisi e tracciabili.

## Sicurezza e privacy

- Variabili sensibili sempre in `.env` o nel secret manager, mai hardcoded.
- Non leggere, mostrare o committare `.env`, database reali, backup, URL iCal o JSON di account di servizio.
- Non inserire dati identificativi di pazienti, iscritti o minori nella documentazione, nei test o nei log.
- Mantenere CSRF sui form mutativi, rate limiting sulle route sensibili e protezione delle route admin.
- Le immagini con partecipanti e le testimonianze richiedono autorizzazione adeguata.
- Prima della produzione risolvere le attività P0 di sicurezza indicate nella roadmap.

## SEO e misurazione

- Un solo `h1` descrittivo per pagina; gerarchia `h2`/`h3` semantica.
- Mantenere titolo, meta description, canonical e Open Graph specifici.
- Mantenere `MedicalBusiness` per lo studio e `Service` per la consulenza del sonno.
- Aggiungere fonti affidabili quando si fanno affermazioni cliniche o di sicurezza.
- Le CTA principali devono avere `data-conversion` e distinguere corsi, call sonno, prestazioni e aziende.
- `static/js/conversion-tracking.js` non deve aggirare il consenso cookie.

## Checklist prima di concludere

- Controllare la gerarchia corsi/sonno/prestazioni e le CTA concorrenti.
- Per modifiche pubbliche verificare almeno 1440 px e 390 px: header, menu, immagini, form, sticky CTA, footer e overflow.
- Controllare contrasto, tastiera, focus, label, target touch e testi dinamici.
- Verificare palette, font, componenti e immagini rispetto al brand system.
- Verificare un solo `h1`, metadati e dati strutturati nelle pagine commerciali.
- Eseguire test pertinenti, `pytest` e `git diff --check`.
- Non considerare conclusa una modifica estetica importante senza controllo visivo desktop e mobile.
- Se cambia una scelta durevole, aggiornare `docs/DECISIONS.md`; se cambia lo stato, aggiornare `docs/ROADMAP.md`; se cambiano testi o immagini, aggiornare `docs/CONTENT_AND_ASSETS.md`.

## Comandi essenziali

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 -m flask --app app run
pytest
git diff --check
```

Migrazioni, configurazione e deploy sono documentati in `docs/OPERATIONS.md`.
