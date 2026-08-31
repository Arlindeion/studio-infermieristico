# Registro delle decisioni — proposta di aggiornamento

> **Documento di revisione, non applicato alla repository.**
>
> Base di riferimento: `main`, 31 agosto 2026, con `docs/DECISIONS.md` corrente fermo a D-105.
> Questo file contiene esclusivamente le nuove decisioni da aggiungere dopo D-105.
> I file originali della repository non sono stati modificati.

## D-106 — Prima si chiudono i collaudi correnti, poi si evolve l’area Pazienti

- Data: 2026-08-31.
- Stato: approvata dal committente; non implementata.
- Decisione: non modificare l’area `Pazienti`, il relativo modello dati o le funzioni gestionali future finché non sono stati completati e superati i test e i collaudi delle funzioni attualmente implementate nel sito. L’evoluzione dell’area pazienti resta un lavoro successivo e non deve interferire con la chiusura dei flussi P0/P1 già aperti.
- Motivo: evitare che una migrazione strutturale dell’anagrafica o l’introduzione di funzioni cliniche aumentino la superficie di regressione mentre corsi, sonno, privacy, produzione e controlli finali devono ancora essere chiusi.
- Conseguenze: fino alla chiusura positiva dei collaudi correnti, `PersonaCorso`, la scheda paziente esistente e le relative route restano invariati salvo correzioni necessarie a completare i test. Solo dopo il gate si avvia, nell’ordine approvato: nuovo modello anagrafico → Scheda Paziente 2.0 → note/cartella infermieristica → lettore Tessera Sanitaria → documenti/Google Drive → consensi/firma → scanner/mobile → promemoria.
- Collegamenti: `ROADMAP.md`, D-092, D-095, D-096, D-097, D-103, D-105.

## D-107 — L’anagrafica futura usa una vera entità Persona e relazioni familiari

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo D-106.
- Decisione: superare `PersonaCorso` con una migrazione funzionale e controllata verso una vera entità `Persona`, rinominando in quella fase sia la classe sia la tabella e riallineando le relazioni. Non eseguire una rinomina isolata prima dell’evoluzione dell’area pazienti.
  Separare `nome` e `cognome`; aggiungere data di nascita strutturata e facoltativa, sesso anagrafico, luogo di nascita con comune/Stato e provincia, residenza con indirizzo/CAP/comune/provincia tutti facoltativi. Il codice fiscale resta il principale identificatore di duplicati. Il numero della Tessera Sanitaria non è richiesto nella prima versione.
  Per i minori usare relazioni esplicite verso adulti con ruolo `madre`, `padre`, `tutore`, `affidatario` o `altro`; un adulto può essere collegato a più minori e un minore a più adulti. È previsto un contatto principale. Telefono ed email possono appartenere sia al paziente sia al tutore.
- Motivo: il modello attuale nasce dalla gestione corsi e non rappresenta in modo sufficiente pazienti, minori, tutori e dati anagrafici necessari al futuro gestionale.
- Conseguenze: D-092 resta valida per il sistema corrente, ma viene superata nella sola scelta di mantenere permanentemente `PersonaCorso` quando inizierà la migrazione funzionale prevista. I record esistenti devono essere migrati con Alembic, test di conservazione dati, rollback e verifica dei collegamenti storici.
- Collegamenti: `app.py`, `ROADMAP.md`, D-092, D-095, D-096, D-106.

## D-108 — I duplicati sono segnalati, revisionabili e fondibili con audit

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo D-106.
- Decisione: il codice fiscale coincidente genera sempre un avviso forte di possibile duplicato. In assenza di una corrispondenza esatta del CF, mostrare l’avviso quando coincidono almeno due campi tra nome, cognome, data di nascita, telefono ed email.
  L’avviso offre `Unisci anagrafica` e `Non unire`. `Non unire` viene memorizzato per quella coppia e non viene riproposto finché i dati rilevanti non cambiano. La fusione avviene campo per campo, consentendo di scegliere quale valore mantenere e di conservare più recapiti quando appropriato.
- Motivo: ridurre duplicati senza usare corrispondenze deboli come fusione automatica.
- Conseguenze: ogni fusione è reversibile e auditata, inclusa la provenienza dei valori selezionati. Nessuna corrispondenza basata solo su telefono, email o nome provoca una fusione automatica.
- Collegamenti: D-092, D-095, D-096, D-107.

## D-109 — La Scheda Paziente 2.0 è la dashboard operativa unificata

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo il nuovo modello anagrafico.
- Decisione: organizzare la futura scheda paziente nelle aree `Panoramica`, `Anagrafica`, `Attività`, `Cartella infermieristica`, `Note`, `Consensi e documenti`.
  Prevedere azioni rapide per nuovo appuntamento, iscrizione a corso e nuova call sonno con anagrafica già preselezionata.
  La timeline è unica e filtrabile. Di default mostra `Prestazioni sanitarie` e `Servizi / corsi`; le `Attività amministrative` sono disponibili ma nascoste all’apertura. Gli eventi amministrativi utili alla ricostruzione operativa sono distinti dall’audit tecnico.
  La ricerca globale deve poter riconoscere anche una Tessera Sanitaria letta dal dispositivo previsto da D-113.
- Motivo: evitare pagine e storici separati per ogni tipo di pratica e rendere la scheda il punto di lavoro principale sulla persona.
- Conseguenze: appuntamenti, corsi, sonno e attività amministrative sono normalizzati in una rappresentazione comune per la timeline senza perdere le entità di origine.
- Collegamenti: D-092, D-097, D-106, D-107, D-108.

## D-110 — La cartella infermieristica è strutturata, versionata e mono-professionista

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo Scheda Paziente 2.0.
- Decisione: il gestionale resta mono-professionista; non introdurre multiaccount, ruoli o permessi tra professionisti.
  La Cartella infermieristica usa tab dedicate e un riepilogo clinico sempre visibile. Comprende anamnesi distinta con campi strutturati e testo libero; aree patologica, farmacologica, allergologica, chirurgica e familiare; condizioni attive separate da pregresse/risolte; allergie strutturate e sempre evidenziate; farmaci con dose, frequenza, via, date, note e stato `attivo`, `sospeso` o `concluso`; terapie infermieristiche; dispositivi sanitari come PICC, CVC, PEG, catetere e stomia con campi facoltativi; medicazioni/lesioni e fotografie cliniche collegate alla relativa scheda.
  Le fotografie cliniche non compaiono nella timeline generale. I parametri vitali longitudinali sono esclusi dalla prima versione. È prevista ricerca testuale interna.
  Le note possono essere amministrative o cliniche e sono storicizzate: ogni modifica conserva la versione precedente. Non viene introdotta una chiusura definitiva della nota.
- Motivo: costruire uno strumento infermieristico utile senza replicare una cartella medica generalista né introdurre complessità multiutente non necessaria.
- Conseguenze: l’introduzione di dati sanitari richiede prima dell’implementazione verifica di privacy, sicurezza, conservazione, backup, accesso e procedure coerenti con il trattamento di dati particolari.
- Collegamenti: D-103, D-106, D-107, D-109.

## D-111 — Appuntamento programmato e prestazione eseguita restano entità concettualmente distinte

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo D-110.
- Decisione: usare un modello comune per le prestazioni eseguite, senza creare un modulo clinico differente per ogni prestazione nella prima versione.
  Dalla pratica prenotata l’admin dispone del comando `Registra prestazione eseguita`. Se esiste un appuntamento, la nuova registrazione viene precompilata automaticamente con paziente, tipo di prestazione, data, ora e riferimento alla prenotazione; la registrazione effettiva resta una scelta dell’operatore.
  Gli stati previsti sono `prenotata`, `eseguita`, `non eseguita`, `annullata`, `no-show`. L’esito usa testo libero.
  Distinguere `referto` da `allegato`; un referto ricevuto successivamente può essere associato alla prestazione originaria. Prevedere una coda `Referti da verificare/associare`.
- Motivo: evitare doppio inserimento dei dati senza confondere ciò che era programmato con ciò che è realmente avvenuto.
- Conseguenze: lo storico clinico può ricostruire la provenienza della prestazione e mantenere separati prenotazione, esecuzione, note e documenti.
- Collegamenti: D-084, D-092, D-109, D-110.

## D-112 — Documenti e consensi usano Drive per i file e il database per metadati e relazioni

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo le funzioni cliniche di base.
- Decisione: archiviare i file fisici su Google Drive e mantenere nel database metadati, tipo, relazione con paziente/pratica, identificativo Drive, versioni e stato.
  Creare una cartella automatica per paziente identificata solo dall’ID interno, organizzata per anno e categoria. Standardizzare i nomi dei file conservando il nome originale nei metadati. I documenti sono apribili direttamente dalla scheda paziente.
  Supportare drag-and-drop, tipi file ammessi controllati e limite di 25 MB. Conservare le versioni precedenti. Una cancellazione sposta il documento in archivio/cestino recuperabile per 90 giorni e lascia audit. I tempi di conservazione sono differenziati per categoria e le scadenze vengono segnalate quando applicabili.
  Prevedere successivamente acquisizione da scanner e da interfaccia mobile sicura; il sistema può suggerire paziente e categoria, ma richiede sempre conferma.
  Non registrare nell’audit il semplice download o il comando di stampa.
  Per i consensi conservare la versione esatta dell’informativa/modulo accettato. Supportare consenso web, upload del cartaceo firmato e, in una fase successiva, firma su tavoletta. Prima della firma mostrare il documento completo; generare un PDF con firma e data/ora. Non conservare la firma come immagine separata riutilizzabile. La copia firmata può essere inviata via email su richiesta.
- Motivo: separare storage dei file e modello applicativo, mantenere versioni e tracciabilità e rendere l’archivio accessibile dal gestionale senza esporre nomi dei pazienti nella struttura delle cartelle.
- Conseguenze: prima dell’uso con documenti sanitari reali devono essere verificati configurazione Drive/Workspace, privilegi minimi, accordi e responsabilità privacy, procedure di backup/restore e tempi di conservazione. L’hardware della tavoletta viene scelto successivamente.
- Collegamenti: D-097, D-102, D-103, D-106, D-109, D-110.

## D-113 — La Tessera Sanitaria supporta banda magnetica e barcode nella prima versione

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo Scheda Paziente 2.0 e cartella infermieristica.
- Decisione: implementare una prima versione del lettore Tessera Sanitaria tramite lettore USB della banda magnetica e supporto a scanner barcode; il chip TS-CNS e l’accesso PC/SC restano esclusi.
  Il flusso è `lettura → anteprima → verifica duplicati → conferma operatore`. La traccia grezza non viene mai salvata nel database né nei log.
  Se il codice fiscale identifica un paziente già presente, mostrare un avviso con possibilità di aprire la scheda esistente o proseguire consapevolmente. Il lettore è utilizzabile anche come ricerca rapida globale.
- Motivo: velocizzare identificazione e inserimento anagrafico usando dispositivi semplici e compatibili con un’applicazione web, senza introdurre nella v1 dipendenze da smart card CNS.
- Conseguenze: la funzione non salva automaticamente l’anagrafica e non memorizza il numero della Tessera Sanitaria se non necessario. La validazione dei dati e la gestione duplicati seguono D-108.
- Collegamenti: D-107, D-108, D-109.

## D-114 — Promemoria paziente visibili in agenda e Calendar non bloccano mai gli slot

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo le altre estensioni dell’area pazienti.
- Decisione: introdurre nella scheda paziente un’area `Da fare` con attività manuali e avvisi automatici. Gli avvisi automatici possono essere chiusi con `Non mostrare più`.
  I promemoria collegati al paziente vengono sempre sincronizzati con Google Calendar e mostrati anche nell’agenda locale. Sono eventi senza orario/all-day e vengono creati su Google Calendar come liberi/trasparenti.
  Un promemoria non deve mai ridurre la disponibilità prenotabile: il motore locale degli slot lo esclude esplicitamente dai conflitti indipendentemente dal comportamento di Google Calendar.
- Motivo: rendere visibili richiami, controlli e attività da fare senza intasare l’agenda e senza sottrarre disponibilità agli utenti.
- Conseguenze: appuntamenti, blocchi agenda e promemoria hanno semantiche distinte; solo appuntamenti e blocchi compatibili con le regole di disponibilità possono occupare slot.
- Collegamenti: D-080, D-081, D-082, D-084, D-106, D-109.

## D-115 — Audit e ciclo di vita del paziente accompagnano l’evoluzione gestionale

- Data: 2026-08-31.
- Stato: approvata dal committente; pianificata dopo D-106.
- Decisione: mantenere il gestionale mono-professionista ma rafforzare l’audit delle operazioni importanti. Registrare data/ora, tipo di operazione e, dove necessario, valore precedente e nuovo per modifiche anagrafiche e cliniche; registrare in dettaglio fusioni, documenti, consensi e modifiche delle note senza duplicare nei log dati non necessari.
  La fusione di anagrafiche resta reversibile. La cancellazione ordinaria del paziente non è prevista: una persona può essere resa inattiva/archiviata e i dati vengono successivamente anonimizzati o eliminati secondo le policy applicabili.
- Motivo: la presenza di informazioni cliniche e documenti richiede una ricostruzione più affidabile delle modifiche senza introdurre complessità multiutente che non serve allo Studio.
- Conseguenze: le policy di audit e conservazione devono essere definite e collaudate prima di usare le nuove funzioni con dati reali.
- Collegamenti: D-083, D-097, D-103, D-106, D-108, D-110, D-112.
