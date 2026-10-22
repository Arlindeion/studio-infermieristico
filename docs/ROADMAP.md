# Roadmap

Revisione documentale: 20 ottobre 2026. Priorità approvata: pubblicare su `https://scstudioinfermieristico.it` nel minor tempo possibile, chiudendo i rischi e i controlli necessari a ricevere richieste reali. [D-123](DECISIONS.md#d-123--pubblicare-il-dominio-prima-delle-estensioni-paypal-sospeso) sostituisce il precedente vincolo del checkpoint del 15 settembre e l'esclusività di lavorazione di D-118; non cambia la gerarchia commerciale corsi → sonno → prestazioni.

## Perimetro della prima pubblicazione

- Conservare i flussi già implementati e l'attuale identità visiva; correggere bug, sicurezza, integrità e impedimenti all'uso.
- Chiudere il deploy privato e lo smoke test dell'attuale Pazienti 2.0, senza aggiungere cartella infermieristica, documenti, ruoli o nuove tranche.
- Per il sonno usare il bonifico con verifica manuale. **PayPal è sospeso fino a nuovo ordine**: nessuna configurazione, implementazione o prova PayPal è un requisito del lancio; i link eventualmente presenti non devono attivare l'opzione.
- Campagna, nuove creatività, testimonianze sonno, attivazione GA4/Meta e redesign non sono prerequisiti della pubblicazione. Analytics non configurati restano inattivi; eventuali attivazioni successive devono rispettare il consenso.
- Restano obbligatori protezione dei dati, autenticazione, CSRF, persistenza locale, correttezza di corsi/prenotazioni, autorizzazioni dei contenuti effettivamente pubblicati e accessibilità essenziale.

Il lavoro locale preparatorio può procedere insieme alla riconciliazione Render. Non occorre aspettare il deploy Pazienti per correggere un bug già riproducibile, aggiornare documenti o preparare il collaudo finale.

## Stato verificato e limiti

La candidata `016f93d` è stata committata e pubblicata su `origin/main`. La patch PR #16 (`eefab033`, 2 commit, 9 file), basata su `dd6c2be`, è stata applicata e adattata alla nuova priorità. I suoi log CI attestano 468 test Python superati, 7 PostgreSQL opt-in saltati e 54 JavaScript superati **sulla versione della PR**, non sulle successive modifiche. La verifica aggiornata è riportata nella [checklist](PRE_GO_LIVE_CHECKLIST.md) e nel [resoconto delle prove autonome](TEST_AUTONOMI_2026-10-20.md). La console del servizio Render di produzione ha restituito il commit `edd800444ab95de7ced8654c64b9144c2c9363c6`: il push della candidata non equivale al suo deploy.

Le conferme precedenti su grafica Admin 2.0, policy professionali/legali, cache admin e collaudi SMTP/Calendar restano evidenze storiche; non sono invalidate da questa revisione. Commit live, revisione Alembic, dati e configurazione corrente di Render restano da riconciliare. Non dichiarare il deploy eseguito o assente senza evidenza del servizio.

## P0 — percorso minimo verso il dominio

| Ordine | Attività | Stato | Criterio di uscita |
|---|---|---|---|
| R1 | Consolidare la candidata locale e le regressioni di sicurezza | Completato | Patch applicata e verificata localmente; esiti aggiornati nella checklist. Identificare il commit definitivo prima del deploy. |
| R2 | Riconciliare Render e database | Da fare | Commit, Alembic, configurazione non segreta, protezioni, health e conteggi quando previsti noti; preflight eseguito prima delle migrazioni del primo cutover. |
| R3 | Distribuire e collaudare l'attuale Pazienti 2.0 in privato | In corso | Candidata approvata, schema coerente, collegamenti v2 e storico Calendar manuale, audit, archiviate in sola lettura, logout/Indietro e desktop/mobile verificati sul servizio. Nessuna nuova funzione. |
| R4 | Collaudare i flussi che riceveranno richieste reali | Da fare | Prestazioni, corsi, lista d'attesa, nascita e sonno funzionanti; bonifico disponibile e verificabile manualmente; email/Calendar e recovery testati senza perdita dati. |
| R5 | Proteggere i dati e chiudere il collaudo finale | Da fare | Sintetici identificati e puliti con autorizzazione; rollback noto; PITR/backup/restore prima di dati reali o interventi su dati da preservare; nessun bug bloccante. |
| R6 | GO, dominio e verifica successiva | Da fare | Decisione esplicita; configurazione produzione, DNS/HTTPS, redirect/canonical, cookie, URL email, indicizzabilità delle sole pagine pubbliche e monitoraggio verificati. |

### Distinzione obbligatoria nel preflight

Seguire [OPERATIONS.md](OPERATIONS.md#paz-a3a4--preflight-e-cutover-diretto-sul-database-render-vuoto):

1. **Primo cutover legacy:** il preflight deve precedere `db upgrade`. Se rileva dati, fermarsi e decidere come preservarli; nessun backfill automatico o cancellazione per forzare il gate.
2. **Schema A4/post-A4 già applicato:** `--allow-applied` può restituire `cutover_gia_applicato` anche con dati presenti. Non significa database vuoto e non richiede un nuovo backfill; eventuali conteggi per inventario/cleanup vanno richiesti separatamente.
3. Un database realmente vuoto non richiede un dump vuoto; registrare revisione, assenza di dati e rollback tecnico. Con dati da preservare, protezione e ripristino precedono operazioni rischiose.

### Rilievi da non perdere nel passaggio al lancio

Il controllo pubblico Render del 22 ottobre ha rilevato il riuso dei moduli completi d’iscrizione nei ricontatti senza date. Correzione locale D-130: modulo minimo condiviso nelle quattro pagine corso, tematica preselezionata e salvataggio senza dati amministrativi/sanitari né posti occupati. Restano commit/deploy e verifica sul servizio. L’età obbligatoria nella call sonno è invece confermata dal committente: corretto il documento di flusso obsoleto, nessuna modifica al modulo sonno. Questo aggiornamento non attesta il completamento di R4 o il GO.

L'[audit del 18 settembre](AUDIT_PRE_LANCIO_2026-09-18.md) resta un inventario storico. La candidata locale include le correzioni per data impossibile nell'API call, esclusione `ignore_id` senza cancellare altre occupazioni, logo admin leggibile e input CSRF non ASCII; la chiusura richiede i test della candidata e il collaudo privato pertinente.

Il conflitto tra richieste simultanee prestazione/call è **riprodotto su PostgreSQL usa-e-getta**: nove prove su nove accettano due richieste per lo stesso orario (prestazione/prestazione, call/call e misto). La prova sincronizza l'esecuzione dopo il controllo reale della disponibilità senza falsificarne il risultato; non misura la probabilità nel traffico normale. Il committente ha accettato questo rischio per il lancio e rinviato la correzione al post-pubblicazione (D-125): **non blocca R4 né il GO e non è risolto**. I nomi invisibili nelle schede dell'agenda settimanale popolata sono stati corretti e ricollaudati localmente a 1440×900 e 390×844, con 42 appuntamenti da 15 a 240 minuti; resta la verifica della correzione dopo il deploy. Dettagli nel resoconto. Il fallback Calendar senza cache fresca richiede riconciliazione e conferma manuale: non trasformare l'indisponibilità di Google in un errore che perda la richiesta locale. Per ordine del committente, Calendar reale non deve essere modificato dagli agenti: ulteriori collaudi di scrittura restano sospesi e non vengono eseguiti in autonomia (D-124).

## Piano canonico 1–20

Numeri e stati storici non vengono riutilizzati. “Completato” indica il relativo criterio documentato; il controllo sulla candidata di rilascio è distinto.

| Step | Area | Stato | Prossimo controllo / perimetro |
|---|---|---|---|
| 1 | Policy e vincoli operativi | Completato | Validazione professionale/legale confermata il 9 settembre; condizioni versionate e prezzi restano invariati. |
| 2 | Bootstrap amministratore | Completato | Verificare accesso effettivo sulla candidata; nessuna credenziale predefinita. |
| 3 | Infrastruttura staging/produzione | Completato | Riconciliare pannello corrente in R2. |
| 4 | Migrazioni Alembic | Completato per il repository | Applicazione su Render secondo preflight e procedura R2–R3. |
| 5 | Strategia backup e restore | Completato come procedura/collaudo storico | Confermare protezione attuale quando necessaria in R5. |
| 6 | Configurazione runtime | In corso | R2, poi produzione sul dominio in R6. |
| 7 | Staging privato | Completato | Mantenerlo protetto durante il collaudo. |
| 8 | Email e Calendar | Completato nello storico | Smoke sulla candidata e recovery in R4. |
| 9 | Prestazioni | Completato nello storico | Richiesta, durata manuale, conferma, modifica e annullamento in R4. |
| 10 | Corsi e lista di interesse | Completato nello storico | Singolo/coppia, capienza, attesa, CSRF e comunicazioni in R4. |
| 11 | Percorso nascita | Completato nello storico | Regressione sul modulo privato, capienza e consensi in R4. |
| 12 | Consulenza del sonno | In corso | Chiudere il percorso con bonifico manuale; PayPal sospeso. |
| 13 | Resilienza | Completato nello storico | Verificare salvataggio locale e recupero sulla candidata in R4. |
| 14 | Privacy, cookie e dati | Completato come validazione policy | Protezioni tecniche, dati, URL privati e tracciamenti sul dominio. |
| 15 | Contenuti e autorizzazioni | In corso (P1) | Contenuti pubblicati autorizzati; nuove testimonianze/materiali dopo il lancio. |
| 16 | Visual, accessibilità e SEO | In corso (P1) | Prima del GO: moduli e navigazione usabili a 390×844 e 1440×900; rifiniture successive. |
| 17 | Processo e misurazione commerciale | In corso (P1) | Bonifico e gestione manuale al lancio; nuove misurazioni dopo stabilizzazione. |
| 18 | Campagna iniziale | Da fare (P1, dopo pubblicazione) | Non blocca R6; creatività, misurazione con consenso e spesa richiedono verifica separata. |
| 19 | Controllo finale pre-lancio | Da fare | R1–R5 conclusi e GO/NO-GO. |
| 20 | Dominio e monitoraggio | Da fare | R6, obiettivo prioritario corrente. |

## P1 — dopo la stabilizzazione del dominio

- Correggere le doppie richieste simultanee prestazione/call con controllo e salvataggio atomici condivisi, poi ripetere le tre combinazioni su PostgreSQL. Rischio accettato per il lancio in D-125; nel frattempo ricontrollare le sovrapposizioni prima della conferma manuale. Nessuna stima quantitativa della probabilità disponibile.
- Rifiniture estetiche oltre i difetti che impediscono lettura o uso, ottimizzazione foto e Open Graph, sitemap e SEO aggiuntiva.
- Campagna sonno, nuove creatività, testimonianze reali autorizzate e attivazione delle misurazioni con consenso.
- Ottimizzazioni del funnel e riduzione del carico manuale basate sui primi utilizzi.
- Storage distribuito per il rate limiting prima di aumentare worker/istanze; l'attuale assetto resta un solo worker.
- Branch protection e processo di revisione continuativo.

## P2 e sospensioni

Nuove funzioni Pazienti, cartella infermieristica, documenti, ruoli/multiaccount, automazioni, nuove landing e rateizzazione restano successive al lancio e alla verifica del bisogno.

**PayPal: sospeso fino a nuovo ordine**, non pianificato automaticamente al termine dei P0. La ripresa richiede decisione, implementazione/configurazione e collaudo dedicati. I riferimenti nelle decisioni e condizioni storiche non ne attestano l'operatività.

## Aggiornamento e GO

[PRE_GO_LIVE_CHECKLIST.md](PRE_GO_LIVE_CHECKLIST.md) raccoglie le prove eseguibili; [ROADMAP_POST_PATCH_2026-10-20.md](ROADMAP_POST_PATCH_2026-10-20.md) riconcilia la roadmap allegata con la candidata locale. Nessuna preparazione locale, CI verde o revisione documentale equivale a commit, push, merge, deploy, DNS o autorizzazione al GO.
