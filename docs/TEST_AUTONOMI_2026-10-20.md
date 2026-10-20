# Prove autonome e pulizia — 20 ottobre 2026

## Esito

Esito originario: **NO-GO sulla candidata `016f93d`**, con due difetti riprodotti e verifiche di rilascio ancora aperte. Decisione successiva del committente (D-125, 20 ottobre): la concorrenza è un rischio accettato per il lancio, da correggere dopo la pubblicazione; non è più un blocco al GO. Successivamente è stata richiesta e verificata la correzione dei nomi nell'agenda, descritta sotto. Restano i controlli di rilascio sulla versione effettivamente distribuita. Nessun deploy è stato eseguito.

| Prova | Esito | Perimetro |
|---|---|---|
| Suite Python | 472 passed, 7 skipped in 38,59 s | SQLite in memoria, dotenv e scheduler disabilitati. |
| PostgreSQL opt-in A1/A2 | 7 passed in 3,54 s | Cluster PostgreSQL locale nuovo, UTF-8, solo socket Unix; schemi temporanei. |
| JavaScript | 54 passed | Suite Node del repository. |
| Due richieste simultanee sullo stesso orario | **9 prove fallite su 9** | Tre prestazione/prestazione, tre call/call, tre miste; due inserimenti accettati ogni volta. |
| Admin popolato, 1440×900 e 390×844 | **Difetto di leggibilità** | 35 appuntamenti, 12 call e 12 corsi sintetici; nomi invisibili nelle schede settimanali. Corsi senza overflow globale; nessun errore JavaScript osservato. |

## P1 post-pubblicazione — doppia prenotazione concorrente, rischio accettato

Le route `/prenota` e `/prenota-call-sonno` controllano la disponibilità con `slot_occupato_db` e salvano successivamente senza una protezione atomica condivisa contro la concorrenza tra richieste. La prova usa i veri controlli e i veri inserimenti PostgreSQL; una barriera a due thread, immediatamente dopo il controllo, forza entrambi i client a completarlo prima di proseguire. Non viene sostituito né falsificato il risultato della disponibilità.

Sono state usate nove date lavorative valide nell'agosto 2099, sempre alle 10:00. Entrambi i client, dotati di sessioni e token CSRF distinti, ricevono il redirect di successo; le query successive confermano due occupazioni nello stesso orario. Sono simulate soltanto Calendar e le notifiche email. Il caso misto dimostra che un vincolo separato su ciascuna tabella non sarebbe sufficiente. La prova dimostra una sequenza concorrente possibile, non una frequenza statistica di collisione nel traffico normale.

Dopo la pubblicazione, secondo D-125: rendere atomico il controllo/salvataggio tra prestazioni e call, preservare la gestione dei conflitti e ripetere le tre combinazioni su PostgreSQL. Nel frattempo ricontrollare disponibilità e sovrapposizioni prima della conferma manuale. Nessuna correzione è stata implementata in questa sessione di collaudo; il rischio è accettato, non eliminato.

## P1 — nomi invisibili nell'agenda settimanale

Con appuntamenti di 60 minuti e nomi lunghi, nelle schede settimanali sono visibili orario, stato e collegamento, ma non il nome. Il nodo `strong` contenente nome e servizio è presente nel DOM e nel nome accessibile, ma il suo rettangolo ha altezza zero. Difetto osservato a 1440×900 e 390×844; l'agenda mobile mantiene lo scorrimento interno senza overflow globale. Le regole coinvolte sono quelle di `.admin-week-event` e dei suoi figli in `static/css/admin.css`.

Prima del GO: garantire una quota di spazio leggibile al nome, con eventuale troncamento controllato, senza nasconderlo per privilegiare informazioni secondarie. Ricontrollare appuntamenti brevi/lunghi, schede affollate, tastiera e touch. Non sono state apportate correzioni grafiche.

## Render: inventario e pulizia autorizzata

Servizio verificato dalla console del pannello Render: `sc-studio-infermieristico-production`. La console ha restituito il commit live `edd800444ab95de7ced8654c64b9144c2c9363c6`, diverso dalla candidata su GitHub. Non sono state eseguite migrazioni, modifiche di configurazione, deploy o operazioni DNS.

Il committente ha indicato come criterio iniziale il nome contenente `test` e l'anno 2027. L'inventario ha trovato otto appuntamenti corrispondenti già annullati e due corsi corrispondenti già archiviati, tutti senza un ID Calendar locale. Dei sei iscritti collegati ai corsi, tre non contenevano `test` nel nome: il committente ne ha visionato i nominativi in chat e ha confermato la cancellazione. I nominativi non sono riportati nella documentazione.

Sono stati verificati i vincoli prima della transazione: nessuna richiesta aziendale collegata ai due corsi, nessuna autorizzazione immagini o presenza accompagnamento collegata alle sei iscrizioni. Il comando ha bloccato le righe selezionate, ricontrollato esattamente identificativi e criteri e cancellato con SQLAlchemy esclusivamente sei iscrizioni, due corsi e otto appuntamenti. Sono state aggiunte sedici voci di audit senza nominativi. I conteggi successivi confermano l'assenza dei sedici record e la conservazione dei tre altri appuntamenti. Anagrafiche, consensi e storico preesistente non sono stati cancellati; non si dichiara una pulizia generale di ogni dato sintetico.

Il processo di pulizia ha disabilitato scheduler e caricamento dotenv e bloccato le connessioni socket Python prima dell'importazione dell'app. Non ha chiamato helper o route Calendar/email. **Zero operazioni Calendar effettuate**, secondo D-124. Non sono stati letti segreti, file `.env`, credenziali Calendar o backup. L'eliminazione dei sedici record dal database è definitiva: non è stato creato un backup durante questa attività e non si attesta un ripristino disponibile.

Il database temporaneo di collaudo è stato verificato senza tabelle applicative residue e il relativo server arrestato; l'anteprima SQLite in memoria è temporanea. Nessun dato sintetico delle prove concorrenti o grafiche è stato inserito su Render.

## Gate ancora aperti

Riconciliazione completa dello schema/configurazione Render, collaudo privato della candidata effettivamente distribuita (inclusa la correzione grafica), protezione/ripristino dei dati e verifiche di dominio. La concorrenza non è più un gate pre-lancio per D-125. I test Calendar reali di scrittura restano vietati agli agenti; i test simulati non li sostituiscono. La [checklist](PRE_GO_LIVE_CHECKLIST.md) resta il riferimento dei gate e non viene marcata interamente completata.

## Correzione successiva — nomi dell'agenda visibili

Su richiesta del committente è stata corretta esclusivamente la resa delle schede: righe Grid a dimensione intrinseca e allineamento iniziale impediscono che il nome venga ridotto ad altezza zero. Nome e orario restano su una riga; i nomi lunghi usano i puntini senza modificare il testo completo del dettaglio o il nome accessibile. Palette, font, durate, posizioni, azioni e integrazioni restano invariati. Il riferimento all'asset CSS è passato a `6.5` per invalidare la cache del browser.

- Python: **472 passed, 7 skipped in 40,61 s**. I sette PostgreSQL opt-in non sono stati rieseguiti per la sola modifica CSS; la loro precedente evidenza separata resta sopra.
- JavaScript: **55 passed**, inclusa una regressione sul contratto CSS che impedisce il collasso della riga del nome.
- Chrome, database SQLite in memoria e Calendar non configurato: **42 schede**, durate 15, 30, 35, 45, 60, 90, 120 e 240 minuti, nomi lunghi; nessun nome con altezza zero o tagliato verticalmente a 1440×900 e 390×844. Nessun overflow globale.
- Dettaglio completo aperto con Invio dopo il caricamento completo dell'agenda; nessun errore JavaScript osservato. Nessuna azione di modifica, spostamento o cancellazione effettuata dal browser.
- Controlli visivi eseguiti su entrambe le dimensioni, senza redesign. Nessuna operazione su Calendar reale o su dati Render. La correzione non è attestata come già distribuita.
