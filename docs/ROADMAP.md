# Roadmap

Stato aggiornato al 16 luglio 2026. Obiettivo indicativo: lancio grafico all'inizio di settembre 2026, non ancora annunciato e quindi modificabile.

## Criterio di priorità

- `P0`: necessario prima dell'esposizione pubblica.
- `P1`: importante per un lancio credibile, rinviabile solo consapevolmente.
- `P2`: evoluzione successiva alla validazione.

## Completato o già implementato

- Identità principale definita: salvia dello studio, tipografia, linea rossa e fotografia reale.
- Header salvia responsive con testo scuro, gerarchia corsi/sonno verificata e footer verde profondo.
- Homepage riorganizzata intorno a corsi e consulenza del sonno.
- Landing verticale sul sonno infantile 0-12 mesi con call gratuita e due formule.
- Prestazioni infermieristiche mantenute in un flusso separato.
- Metadati condivisi, canonical, Open Graph e dati strutturati principali.
- Tracciamento differenziato delle CTA predisposto per GA4 e subordinato al consenso.
- Iscrizioni a corsi collegate alle date e raccolta interesse quando manca una data.
- Gestione in admin di tipologie, capienza e stati dei corsi.
- Flusso privato del percorso nascita con edizioni, incontri, iscritti, presenze ed export PDF.
- Lettura degli impegni Google Calendar e scrittura degli eventi associati.
- Registro operativo per errori parziali di email e sincronizzazioni.
- Configurazione SQLite locale e PostgreSQL-ready.
- Prima riorganizzazione della documentazione in `docs/`.

Le funzionalità già presenti devono comunque superare il collaudo pre-lancio: “implementato” non equivale automaticamente a “pronto per produzione”.

## Prima del lancio

### P0 — sicurezza, dati e produzione

- Rimuovere la creazione automatica di credenziali admin prevedibili o obbligare l'impostazione sicura al primo avvio.
- Definire hosting, dominio, HTTPS, database PostgreSQL e strategia di backup.
- Generare e verificare migrazioni Alembic reali sullo schema di produzione.
- Configurare tutte le variabili di produzione senza inserire segreti nel repository.
- Verificare privacy, cookie, consenso Analytics e conservazione dei dati raccolti.
- Validare con attenzione professionale le policy di cancellazione, spostamento, rimborso, rate e assenze.
- Verificare autorizzazioni per testimonianze e immagini, in particolare quando compaiono minori.

### P0 — collaudo dei flussi

- Testare end-to-end prenotazione sanitaria, conferma manuale, email e Calendar.
- Verificare la modifica/annullamento da parte del paziente e implementare la finestra temporale concordata se non ancora completa.
- Ricevere e allineare le durate definitive degli slot con Arzamed.
- Testare iscrizione a ogni tipologia di corso, capienza, iscrizione di coppia, corso pieno e lista di interesse.
- Testare open day e modulo privato del percorso nascita con conteggio posti corretto.
- Simulare i fallimenti di email e Calendar verificando che il dato principale non venga perso.
- Verificare che gli appuntamenti domiciliari e le aziende non entrino nei flussi individuali.

### P1 — contenuti, design e SEO

- Sostituire il placeholder dei laboratori con una fotografia definitiva autorizzata.
- Valutare e assegnare le fotografie aggiuntive prima del push grafico finale.
- Inserire testimonianze reali autorizzate senza alterarne il significato.
- Controllare tutte le pagine a 1440 px e 390 px, inclusi menu, form, tabelle admin, footer e stati vuoti.
- Verificare contrasto, tastiera, focus, label, target touch e assenza di overflow.
- Verificare titoli, un solo `h1`, meta description, canonical, Open Graph e dati strutturati.
- Controllare testi clinici, qualifiche OPI, fonti e confini della consulenza.
- Preparare immagine social e materiali coordinati per il lancio.

### P1 — lancio commerciale controllato

- Concludere il test del servizio sonno con le famiglie già interessate.
- Raccogliere esito delle call, obiezioni, appropriatezza delle due formule e disponibilità a pagare.
- Definire una risposta operativa standard dopo la richiesta della call.
- Stabilire un piano editoriale sostenibile e un volume di contenuti compatibile con il lavoro clinico.
- Configurare GA4 e verificare gli eventi di conversione prima di qualsiasi campagna.
- Definire un piccolo budget test soltanto dopo avere verificato landing e gestione dei contatti.

## Dopo il lancio

### P2 — validazione e ottimizzazione

- Misurare richieste qualificate, provenienza, tasso call/percorso e carico di lavoro.
- Rivedere prezzi e formato della consulenza sulla base dei dati reali.
- Costruire una mailing list con consenso e segmentazione minima.
- Migliorare il processo di ricontatto e il calendario editoriale.
- Creare landing verticali soltanto per campagne con obiettivo, pubblico e CTA definiti.

### P2 — gestionale commerciale

- Dashboard admin con viste oggi/settimana/mese e sezioni separate.
- Gestione dedicata di consulenze, aziende e ricontatti.
- Modelli corso duplicabili.
- Email automatica opzionale quando cambia un corso con iscritti.
- Export PDF generalizzato degli iscritti e partecipanti.
- Quiz guidato `Da dove parto?`.

### P2 — pagamenti

- Prenotazione dedicata della consulenza dopo la call gratuita.
- Pagamento online per consulenze e corsi selezionati.
- Eventuale rateizzazione.

Non introdurre pagamenti prima che policy, stati, email, capienza e calendario siano stabili.

## Criteri di uscita per il lancio grafico

Il sito può essere considerato pronto quando:

- non usa credenziali prevedibili in produzione;
- i flussi principali salvano sempre i dati e comunicano correttamente lo stato;
- testi, immagini e testimonianze sono autorizzati;
- homepage, corsi, sonno e prestazioni hanno gerarchie distinte;
- test automatici e controlli visuali sono superati;
- analytics e cookie rispettano il consenso;
- ciò che non è automatizzato rimanda in modo chiaro a telefono o WhatsApp;
- Selene è pronta a gestire manualmente il volume di richieste generato.

## Aggiornamento della roadmap

Quando un'attività viene conclusa, spostarla nella sezione completata indicando se è stata anche collaudata. Se una scelta cambia l'ambito o la priorità del progetto, registrarla prima in `DECISIONS.md`.
