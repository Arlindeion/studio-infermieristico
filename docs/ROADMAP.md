# Roadmap

Stato aggiornato al 20 luglio 2026. Il checkpoint interno è il 15 settembre 2026 e richiede sia un sito tecnicamente pronto e sicuro sia una prima campagna online/social coerente con la nuova identità. Non è una scadenza pubblica.

## Gate interno del 15 settembre

Il checkpoint è superato soltanto quando sono veri entrambi i risultati:

1. le attività P0 di sicurezza, dati, produzione e collaudo sono concluse;
2. la campagna iniziale sulla consulenza del sonno è pronta, misurabile e sostenuta da landing, contenuti social e processo di gestione dei contatti coerenti.

La sola finalizzazione grafica non basta. Se un requisito P0 resta aperto, il sito non è pronto all'esposizione pubblica anche se la campagna è stata preparata.

## Criterio di priorità

- `P0`: necessario prima dell'esposizione pubblica.
- `P1`: importante per un lancio credibile, rinviabile solo consapevolmente.
- `P2`: evoluzione successiva alla validazione.

## Completato o già implementato

- Identità principale definita: salvia dello studio, tipografia, linea rossa e fotografia reale.
- Header salvia responsive con testo scuro, gerarchia corsi/sonno verificata e footer verde profondo.
- Homepage riorganizzata intorno a corsi e consulenza del sonno, con schede editoriali differenziate, priorità visiva ai corsi, sezione nascita separata dall'header, calendario accessibile e stato vuoto orientato al ricontatto.
- Landing `call-first` sul sonno infantile 0-12 mesi, con gerarchia responsive e call gratuita come azione dominante.
- Prenotazione breve della call sonno con slot provvisorio, controllo incrociato database/Calendar, gestione admin ed email di conferma.
- Questionario sonno privato sul sito, inviabile solo dopo la call e la scelta della formula.
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

## Piano operativo numerato verso il lancio

Questa è la checklist operativa canonica del progetto. I numeri degli step non vanno riordinati o riutilizzati: negli aggiornamenti si modifica lo stato e si aggiungono note o evidenze. Stati ammessi: `Da fare`, `In corso`, `Completato`, `Bloccato`. Uno step è `Completato` soltanto quando è soddisfatto il relativo criterio di uscita.

1. **Definire policy e vincoli operativi — `Da fare` (P0).** Confermare durate degli slot con Arzamed e validare cancellazioni, spostamenti, rimborsi, rate, assenze e finestra entro cui il paziente può modificare o annullare. **Criterio di uscita:** decisioni approvate e registrate nelle fonti competenti.
2. **Mettere in sicurezza la creazione dell'amministratore — `Da fare` (P0).** Eliminare le credenziali automatiche `admin / cambiami123` e introdurre un'inizializzazione sicura compatibile con sviluppo e produzione. **Criterio di uscita:** nessun database di produzione può avviarsi con credenziali prevedibili e i test dedicati passano.
3. **Definire l'infrastruttura di staging e produzione — `Da fare` (P0).** Scegliere hosting, dominio o sottodominio di staging, dominio pubblico, PostgreSQL, HTTPS, gestione dei segreti e responsabilità operative. **Criterio di uscita:** ambienti e servizi scelti, con configurazione documentata senza credenziali.
4. **Creare e verificare le migrazioni Alembic — `Da fare` (P0).** Generare revisioni reali per lo schema corrente e provarle sia su database vuoto sia su una copia rappresentativa. **Criterio di uscita:** upgrade ripetibile verificato e nessuna dipendenza da `db.create_all()` per evolvere lo schema.
5. **Definire backup e ripristino — `Da fare` (P0).** Stabilire frequenza, conservazione, cifratura e procedura di restore del database PostgreSQL. **Criterio di uscita:** almeno un ripristino di prova completato e documentato.
6. **Preparare la configurazione di produzione — `Da fare` (P0).** Configurare `FLASK_ENV=production`, `SECRET_KEY` stabile, `DATABASE_URL`, SMTP, Calendar e altri segreti nel gestore dell'hosting. **Criterio di uscita:** avvio corretto senza segreti nel repository e log privi di dati personali superflui.
7. **Pubblicare uno staging privato — `Da fare` (P0).** Eseguire il deploy su HTTPS con accesso limitato e indicizzazione disabilitata, usando solo dati fittizi. **Criterio di uscita:** staging raggiungibile, protetto, collegato a PostgreSQL e identificabile tramite commit.
8. **Configurare e collaudare email e Google Calendar — `Da fare` (P0).** Verificare mittente SMTP, lettura Calendar/Arzamed, account di servizio con permessi minimi e scrittura degli eventi. **Criterio di uscita:** prove reali riuscite e anomalie registrate in `RegistroEvento`.
9. **Collaudare il flusso delle prestazioni sanitarie — `Da fare` (P0).** Provare richiesta, conferma manuale, modifica, annullamento, email, Calendar e gestione degli appuntamenti domiciliari. **Criterio di uscita:** percorso completo superato e domicilio mantenuto fuori dalla prenotazione diretta.
10. **Collaudare corsi e lista di interesse — `Da fare` (P0).** Provare ogni tipologia, capienza, coppia, corso pieno, assenza di date, ricontatto e aziende/gruppi. **Criterio di uscita:** conteggi e stati corretti; aziende e gruppi restano nel contatto diretto.
11. **Collaudare il percorso nascita — `Da fare` (P0).** Provare open day, modulo privato non indicizzato, edizioni, incontri, iscritti, presenze e conteggio posti. **Criterio di uscita:** flusso pubblico e privato verificato senza esposizione del modulo completo.
12. **Collaudare il flusso della consulenza del sonno — `Da fare` (P0).** Provare richiesta, blocco provvisorio, conflitti, conferma, modifica concordata, annullamento, call conclusa e questionario privato. **Criterio di uscita:** flusso completo verificato con Calendar reale e disponibilità nazionale invariata.
13. **Verificare la resilienza dei flussi — `Da fare` (P0).** Simulare separatamente indisponibilità e errori di email e Calendar. **Criterio di uscita:** prenotazioni e iscrizioni restano salvate, gli errori secondari sono registrati e l'admin riceve avvisi comprensibili.
14. **Validare privacy, cookie e trattamento dati — `Da fare` (P0).** Verificare informative, consensi, conservazione, Analytics, questionario sonno e dati sanitari con competenza professionale adeguata. **Criterio di uscita:** testi e comportamento approvati; GA4 non si carica prima del consenso.
15. **Finalizzare contenuti e autorizzazioni — `Da fare` (P1).** Sostituire i placeholder, assegnare le fotografie definitive, verificare autorizzazioni per immagini e minori, qualifiche OPI, fonti cliniche e testimonianze reali. **Criterio di uscita:** nessun contenuto pubblico privo di autorizzazione o ancora provvisorio.
16. **Eseguire il collaudo visuale, accessibilità e SEO — `Da fare` (P1).** Controllare tutte le pagine a 1440 px e 390 px, menu, form, admin, stati vuoti, contrasto, tastiera, focus, label, touch target, overflow, `h1`, metadati, canonical, Open Graph e dati strutturati. **Criterio di uscita:** controlli documentati, difetti bloccanti risolti, `pytest` e `git diff --check` superati.
17. **Preparare processo e misurazione commerciale — `Da fare` (P1).** Concludere il test del servizio sonno, raccogliere obiezioni, validare le due formule, definire risposta dopo la call, capacità di gestione, funnel ed eventi GA4. **Criterio di uscita:** processo da richiesta a formula scelta misurabile e sostenibile.
18. **Preparare la campagna iniziale — `Da fare` (P1).** Definire piano editoriale, creatività coordinate, immagine social, procedura per le testimonianze future, geografia e budget del test pubblicitario di tre mesi. **Criterio di uscita:** materiali approvati, CTA coerente e budget attivabile solo dopo la verifica del tracciamento.
19. **Eseguire il controllo finale pre-lancio — `Da fare` (P0).** Riesaminare sicurezza, migrazioni, backup, privacy, flussi, contenuti, misurazione e capacità operativa usando i criteri di uscita del progetto. **Criterio di uscita:** nessun P0 aperto o bloccato e decisione esplicita di procedere.
20. **Aprire il dominio pubblico e monitorare — `Da fare` (P0).** Collegare il dominio definitivo, verificare HTTPS, cookie, redirect, indicizzazione, invii reali, Calendar, log e conversioni; attivare la campagna solo dopo la stabilità iniziale. **Criterio di uscita:** sito pubblico stabile, monitorato e pronto a ricevere richieste qualificate.

## Dopo il lancio

### P2 — validazione e ottimizzazione

- Misurare richieste qualificate, provenienza, tasso call/percorso e carico di lavoro.
- Verificare mensilmente l'obiettivo interno di almeno tre testimonianze reali e autorizzate sulla consulenza del sonno, senza trasformarlo in un obbligo per le famiglie.
- Rivedere creatività, geografia e messaggi durante i tre mesi senza modificare contemporaneamente tutte le variabili.
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

## Criteri di uscita per il lancio

Il sito può essere considerato pronto quando:

- non usa credenziali prevedibili in produzione;
- i flussi principali salvano sempre i dati e comunicano correttamente lo stato;
- testi, immagini e testimonianze sono autorizzati;
- homepage, corsi, sonno e prestazioni hanno gerarchie distinte;
- test automatici e controlli visuali sono superati;
- analytics e cookie rispettano il consenso;
- ciò che non è automatizzato rimanda in modo chiaro a telefono o WhatsApp;
- Selene è pronta a gestire manualmente il volume di richieste generato;
- la campagna iniziale dispone di creatività coordinate, percorso di conversione verificato e misurazione coerente con il consenso.

## Aggiornamento della roadmap

Quando un'attività viene conclusa, spostarla nella sezione completata indicando se è stata anche collaudata. Se una scelta cambia l'ambito o la priorità del progetto, registrarla prima in `DECISIONS.md`.
