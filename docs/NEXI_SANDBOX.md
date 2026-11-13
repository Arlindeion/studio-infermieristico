# Collaudo Nexi HPP prima del contratto

Stato al 13 novembre 2026: collaudo della proposta sonno completato su copia
temporanea, con esito positivo Visa e un'anomalia Mastercard ancora da chiarire
con Nexi. Nessuna attivazione commerciale, nessun deploy, nessun pagamento reale.
D-133.

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
di corsi/prestazioni, rate, produzione o riconciliazione pianificata. Se manca la
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
