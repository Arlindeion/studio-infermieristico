# Collaudo Nexi HPP prima del contratto

Stato al 14 novembre 2026: collaudo della proposta sonno completato su copia
temporanea, con esito positivo Visa e un'anomalia Mastercard ancora da chiarire
con Nexi. Completato anche il collaudo Visa del corso di disostruzione, singolo
34 EUR e coppia 60 EUR. Nessuna attivazione commerciale, nessun deploy, nessun
pagamento reale. D-133 e D-134. Il nuovo percorso D-135 usa acconti 17/30 EUR
e conferma automatica dopo la verifica, come descritto sotto.

## Isolamento

Il profilo `payment_sandbox` usa sempre SQLite in memoria: perde le pratiche
fittizie alla chiusura del processo. Ignora `DATABASE_URL`, non carica `.env`,
disabilita scheduler, invio email e accesso a Calendar. La chiave viene richiesta
con input nascosto oppure letta dalla variabile dedicata `NEXI_SANDBOX_API_KEY`.
Non salvarla nel codice, nei documenti o in file di esempio.

Le configurazioni ordinarie hanno Nexi disattivato. Non basta aggiungere una
chiave alla configurazione del sito: i controlli richiedono il profilo isolato,
il database realmente in memoria e le integrazioni esterne disabilitate.
Non rimuovere né aggirare la protezione staging sul dominio dello studio.

## Avvio locale

Anteprima senza credenziali e senza chiamate Nexi:

```bash
venv/bin/python scripts/nexi_sandbox.py --no-key
```

Il comando stampa il collegamento della proposta fittizia, con le due formule
del percorso. La call iniziale non viene prenotata e nessun evento viene creato.

Verifica delle credenziali, senza avviare un pagamento:

```bash
venv/bin/python scripts/nexi_sandbox.py --probe
```

La verifica cerca un ordine casuale inesistente: il 404 del gateway distingue
credenziali accettate da errori di autenticazione o collegamento. Non certifica
da sola l'inizializzazione HPP o un pagamento completato.

Per il flusso completo, predisporre un'origine HTTPS della sola copia temporanea
di collaudo, raggiungibile dai server Nexi, poi eseguire:

```bash
venv/bin/python scripts/nexi_sandbox.py --public-base-url https://sandbox.example.invalid
```

Sostituire l'origine di esempio con quella reale del collaudo: `.invalid` non è
raggiungibile. Il processo locale ascolta soltanto su `127.0.0.1:5055`; il proxy
HTTPS di test deve inoltrare le richieste a questa porta. Non pubblicare la copia
ordinaria del sito e non collegare database o integrazioni dello studio.
Il parametro è letto solo da `NEXI_SANDBOX_PUBLIC_BASE_URL`, mai dal generico
`PUBLIC_BASE_URL` ereditato da una configurazione reale.

## Percorso verificato dall'applicazione

Questa sequenza riguarda la proposta sonno; il corso mantiene la conferma manuale
dell'iscrizione, come descritto nella sezione dedicata più avanti.

1. Selezione formula e accettazione delle condizioni, con CSRF.
2. Salvataggio locale dell'acquisto e del tentativo prima della richiesta Nexi.
3. `POST /orders/hpp` sandbox con prezzo calcolato dal server, in centesimi,
   `captureType=IMPLICIT` e `recurrence.action=NO_RECURRING`.
4. Redirect verso il solo host `xpaysandbox.nexigroup.com`.
5. Ritorno del browser oppure notifica server-to-server autenticata dal token
   restituito alla creazione. Nel database viene salvato soltanto l'hash del token.
6. Recupero indipendente con `GET /orders/{orderId}` e confronto di ordine,
   valuta, importo e tipo operazione. Solo `EXECUTED` conferma; `AUTHORIZED` resta
   un'autorizzazione senza conferma dell'incasso.
7. Aggiornamento atomico della pratica fittizia e apertura del questionario;
   l'invio email è simulato. Notifiche ripetute non ripetono la conferma.

Gli URL di ritorno e notifica sono distinti. La notifica non richiede cookie,
login o CSRF del browser, ma verifica il token e interroga Nexi prima di aggiornare
la pratica. Un semplice `esito=OK` nella query non conferma nulla.

In caso di timeout all'avvio il tentativo resta aperto: non si crea automaticamente
un secondo ordine. Una risposta negativa verificata permette invece di riprovare.
Un acquisto modificato, revocato o con più operazioni riuscite richiede controllo
manuale. L'esito del pagamento è salvato prima dell'email, il cui errore viene
registrato in `RegistroEvento`.

Non sono implementati rimborsi o contabilizzazioni manuali via API, pagamenti
di altri corsi/prestazioni oltre al collaudo disostruzione descritto sotto,
rate, produzione o riconciliazione pianificata. Se manca la
notifica si può recuperare lo stato dalla pagina personale di esito finché il
processo temporaneo resta acceso.

## Verifiche e limiti

La suite automatica usa risposte simulate: nessun test ordinario contatta Nexi,
Calendar, SMTP o un database reale. La chiave fornita dal committente è stata
verificata separatamente contro il gateway sandbox; non è salvata nel repository.
Alla prima inizializzazione dimostrativa HPP è seguito il collaudo effettivo con
carte ufficiali di test Nexi e ritorno HTTPS alla copia isolata. Il collegamento
temporaneo Cloudflare ha esposto soltanto proposta, cassa/esito, questionario,
condizioni e file statici; le altre route, incluso l'admin, rispondevano 404.

Esiti locali del 13 novembre 2026:

- 48 test mirati Nexi e migrazioni superati.
- Suite completa: 538 superati, 12 saltati, 4 falliti nei test locali preesistenti
  del backup Mac. I quattro errori sono riprodotti copiando soltanto gli script
  backup e i relativi test in una cartella temporanea esterna al progetto;
  l'errore riguarda il confronto temporale del backup. Nessun file backup modificato.
  Esito storico del primo collaudo: nel successivo consolidamento è stato corretto
  l'orologio simulato del test, con suite completa ora superata. Dettagli nella
  [verifica dei backup](OPERATIONS.md#riscontro-locale-del-13-novembre-2026).
- Compilazione dei nuovi moduli e `git diff --check` riusciti.
- Controllo desktop ripetuto con successo in Chrome a 1440 x 900: proposta ed
  esito senza overflow orizzontale o sovrapposizioni, un solo `h1` per pagina,
  campi etichettati e selezione con tastiera (Spazio e frecce), focus visibile.
  L'invio senza accettazione delle condizioni è bloccato; la scelta del percorso
  con affiancamento arriva alla conferma simulata dell'importo corretto, 320 EUR.
  Il gateway in questa prova UI era interamente simulato in una copia locale con
  database in memoria: non è una prova di 3DS o di notifica esterna Nexi.
  Schermate: `output/nexi-sandbox-qa/desktop-proposta-1440.png` e
  `output/nexi-sandbox-qa/desktop-esito-1440.png`.
- Controllo mobile Chrome a 390 x 844 completato: proposta, menu apribile e
  richiudibile, validazione delle condizioni ed esito da 200 EUR. Larghezza del
  documento pari a 390 px, nessun overflow, un solo `h1` per pagina. I controlli
  riutilizzano gli stili del sito. Schermate `mobile-proposta-390.png` e
  `mobile-esito-390.png` nella stessa cartella.

## Collaudo con il gateway Nexi sandbox

| Prova | Risultato osservato |
| --- | --- |
| Visa di test, 200 EUR, autenticazione riuscita | Nexi restituisce `EXECUTED`; la notifica HTTPS arriva con risposta 200 e conferma la pratica prima del ritorno del browser. Il questionario si apre correttamente. |
| Ritorno al sito e ricarica della pagina | Conferma e riferimento conservati; nessun secondo tentativo o questionario creato. |
| Visa di test, 320 EUR, autenticazione fallita | `THREEDS_FAILED`, notifica 200, nessuna conferma o apertura del questionario; ritorno alla proposta e nuovo tentativo disponibili. |
| Annullamento dalla cassa, 200 EUR | `CANCELED`, notifica 200, nessuna conferma. Il nuovo tentativo permette anche di cambiare formula a 320 EUR. |
| Mastercard di test, finali 2903 e 5836, 320 EUR | Entrambe restituiscono `FAILED` nella cassa Nexi prima del passaggio 3DS. Il sito mostra il mancato completamento e non conferma la pratica. |
| Notifica contraffatta | Rifiutata con 403; la pratica già confermata resta invariata. |
| Protezioni pagina esito HTTPS | Verificati `no-store, private`, `noindex, nofollow, noarchive` e `no-referrer`. |

Per i due errori Mastercard, `GET /orders/{orderId}` e
`GET /operations/{operationId}` riportano `paymentCircuit=NOT_DEFINED` e nessun
warning. `GET /payment_methods` include `MC`: non è dimostrato che il circuito sia
disabilitato. La causa resta da chiarire con Nexi o nel back office di test;
il pagamento Mastercard riuscito non è verificato. Riferimenti sandbox:
`NX9b8178925638fa0e` e `NX7fc70b2353dd0a96`.

Evidenze prive di chiavi, token o dati reali:
`output/nexi-sandbox-qa/nexi-e2e-evidence.json`. Le schermate del gateway e degli
esiti sono nella stessa cartella, in particolare `nexi-esito-200-1440.png`,
`nexi-esito-200-mobile.png`, `nexi-3ds-fallita-320-mobile.png` e
`nexi-annullato-200-mobile.png`. Il collegamento HTTPS e i processi temporanei
sono chiusi a fine collaudo; i dati in memoria non vengono trasferiti al sito.

## Corso di disostruzione: acconto e conferma automatica (D-135)

Il parametro `--course` aggiunge un'edizione fittizia futura e ne stampa il
collegamento al modulo. Per provare l'intero percorso:

```bash
venv/bin/python scripts/nexi_sandbox.py --course --public-base-url https://sandbox.example.invalid
```

Vale lo stesso isolamento descritto sopra; sostituire l'origine di esempio con
quella HTTPS temporanea. Con `--course --no-key` si vede il modulo ordinario,
senza cassa Nexi disponibile. Non occorre migrare un database dello studio:
lo script crea lo schema in memoria. D-135 usa i campi esistenti e non introduce nuove migrazioni. La revisione
`b7e2d9c4a601` aggiunge soltanto
la tabella dei tentativi corso; il downgrade rifiuta di eliminarla se contiene dati.

Il prezzo è calcolato sul server: quote totali 3400/6000 centesimi e acconti
1700/3000 centesimi, rispettivamente uno e due posti. Il saldo del restante 50%
(17/30 EUR) è previsto in presenza. Una coppia con una sola persona presente
perde lo sconto: quota singola 34 EUR, acconto già versato 30 EUR e saldo 4 EUR. Le condizioni e i campi obbligatori,
compreso il secondo partecipante, restano quelli del modulo. È aggiunta
l’accettazione esplicita dell’acconto e delle regole di assenza. Versione, istante
e testo integrale delle condizioni sono conservati nella pratica. L'iscrizione viene
salvata prima dell'avvio del gateway. I collegamenti dedicati sono:

- ritorno: `/payments/nexi/sandbox/courses/result/<token>`;
- notifica: `/payments/nexi/sandbox/courses/notification`;
- nuovo tentativo dopo fallimento certo: `/payments/nexi/sandbox/courses/result/<token>/retry`,
  tramite POST con CSRF, sulla stessa iscrizione.

Il gateway verifica importo, valuta e ordine con una richiesta indipendente.
Il pagamento riuscito conferma automaticamente l’iscrizione (`Confermato`)
e crea o collega l’anagrafica del richiedente nella stessa transazione. La scheda
corso riporta il nominativo e, per la coppia, anche il secondo partecipante.
Dopo il commit parte l’email di conferma con acconto, saldo, riferimento e copia
delle condizioni accettate. Ripetere una notifica o il ritorno non reinvia
l’email. Un errore email lascia il posto confermato ed è visibile in admin;
il reinvio manuale non crea un nuovo pagamento. Nessun evento Calendar viene
creato o modificato. Un conflitto anagrafico porta l’esito in verifica manuale. Le regole di capienza non cambiano: la coppia può occupare
l'ultimo posto nominale secondo il flusso esistente; una richiesta in lista
d'attesa non apre la cassa e non viene addebitata.

Fallimenti certi permettono un nuovo tentativo sulla pratica già salvata;
timeout ed esiti incerti lo bloccano per evitare doppi ordini. Una conferma tardiva
di un vecchio ordine, mentre ne esiste un altro attivo, richiede verifica manuale.
Una modifica di data, sede, partecipazione o condizioni dopo l'avvio, oppure una
revoca, porta il pagamento riuscito in verifica manuale. Un tentativo fallito o
scaduto non annulla l'iscrizione e non libera automaticamente i posti: resta
applicabile la gestione manuale ordinaria. Le condizioni commerciali aggiornate sono centralizzate in `course_terms.py`
e condivise da pagina pubblica e copia email. Il preavviso segue quello sonno;
un’assenza senza preavviso valido comporta la perdita dell’acconto, senza saldo
ulteriore. Rimangono salvi i diritti inderogabili del consumatore. Gli ordini
storici a quota intera restano nel precedente flusso manuale e non vengono
convertiti retroattivamente. L’attivazione reale richiede credenziali,
configurazione e collaudo operativi distinti; la chiave disponibile è solo di test.

Collaudo iniziale D-134 del 14 novembre 2026, a quota intera e conferma manuale,
con il gateway Nexi sandbox e carta Visa ufficiale
di test, senza email, Calendar o database dello studio:

| Prova | Risultato osservato |
| --- | --- |
| Singolo, desktop 1440 x 900 | HPP da 34 EUR, autenticazione 3DS riuscita, `EXECUTED`, notifica HTTPS 200 prima del ritorno; iscrizione `Nuova`, un posto. |
| Coppia, mobile 390 x 844 | HPP da 60 EUR, autenticazione 3DS riuscita, `EXECUTED`, notifica HTTPS 200 prima del ritorno; iscrizione `Nuova`, due posti. |
| Modulo ed esito | Un solo `h1`, nessun overflow orizzontale; campi etichettati, consensi utilizzabili anche da tastiera. |

I test automatici coprono anche importi manipolati, CSRF, consensi mancanti,
capienza, lista d'attesa, notifiche contraffatte o ripetute, risposte incoerenti,
retry, guasti di rete e modifica o revoca dell'iscrizione. Le prove automatiche
non contattano servizi reali. Esito finale: 33 test corso superati; suite completa
576 superati e 12 saltati; 55 test JavaScript superati. Migrazioni, compilazione
dei moduli e `git diff --check` verificati. Evidenze senza chiavi, token o dati personali reali:
`output/nexi-course-qa/e2e-evidence.json`, `form-singolo-1440.jpg`,
`esito-singolo-1440.jpg`, `form-coppia-390.jpg` ed `esito-coppia-390.jpg`
nella stessa cartella. Il collegamento HTTPS temporaneo è chiuso a fine collaudo.

### Verifica del nuovo acconto D-135

Il successivo collaudo del 14 novembre 2026 ha verificato il nuovo percorso con
carta Visa ufficiale Nexi e autentica 3DS riuscita:

| Prova | Risultato osservato |
| --- | --- |
| Singolo, desktop 1440 x 900 | Acconto 17 EUR, `EXECUTED`, notifica HTTPS 200 prima del ritorno. Iscrizione `Confermato`, un posto, anagrafica collegata e email generata con invio simulato. Saldo 17 EUR. |
| Coppia, mobile 390 x 844 | Acconto 30 EUR, `EXECUTED`, notifica HTTPS 200 prima del ritorno. Iscrizione `Confermato`, due posti, anagrafica collegata e email generata con invio simulato. Saldo 30 EUR; indicazione del saldo 4 EUR per una sola presenza. |
| Scheda corso admin, desktop e mobile | Entrambe le iscrizioni confermate, nome del secondo partecipante, acconti e saldi visibili. |
| Condizioni e modulo | Condizioni versione 2026-11-14, consenso acconto obbligatorio anche sul server; senza spunta il browser blocca l'invio e porta il focus al campo. Un `h1` e nessun overflow a 1440/390 px. |

Esito automatico finale: 47 test corso, suite completa 602 superati e 12 saltati,
55 test JavaScript superati. Sono verificati anche email fallita e reinvio senza
nuovo ordine, assenza di conferma prima del pagamento, conflitto anagrafico,
richieste di lista d'attesa e compatibilità degli ordini storici a quota intera.
Non sono previste nuove migrazioni per D-135. `git diff --check` e compilazione
dei moduli completati.

Evidenze: `output/nexi-deposit-qa/e2e-evidence.json`, schermate di modulo,
esito, condizioni e scheda corso nella stessa cartella. Sono presenti solo dati
fittizi; nessuna chiave o token privato. Il server e il collegamento HTTPS
temporanei sono stati chiusi. Rimborsi e saldo in presenza restano operazioni
manuali: non sono state aggiunte API di rimborso o addebiti del saldo.

Un'inizializzazione HPP riuscita non prova ricezione delle notifiche, autentica
3DS, incasso bancario reale, disponibilità dell'offerta o commissioni.

Fonti: [registrazione](https://developer.nexi.it/it/area-test/registrazione),
[HPP](https://developer.nexi.it/it/api/post-orders-hpp),
[lettura ordine](https://developer.nexi.it/it/api/get-orders-orderId),
[notifiche](https://developer.nexi.it/it/api/notifica),
[carte di test](https://developer.nexi.it/it/area-test/carte-di-pagamento),
[dettaglio operazione](https://developer.nexi.it/it/api/get-operations-operationId),
[metodi supportati](https://developer.nexi.it/it/api/get-payment_methods),
[collegamento HTTPS temporaneo](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
