# Checklist di pubblicazione sul dominio

Priorità del 20 ottobre 2026: [roadmap corrente](ROADMAP.md), decisione D-123. PayPal è sospeso; il flusso sonno usa il bonifico con conferma manuale. Campagna, nuove funzioni e redesign non sono gate della prima pubblicazione.

## 1. Candidata locale

- [ ] Identificare il commit candidato e chiudere i test locali; i risultati CI della PR #16 non attestano modifiche successive.
- [x] CSRF: proposta orario, lista d'attesa e logout POST; rifiuto di token assenti, errati e non ASCII senza errori 500.
- [x] Redirect login locali/sullo stesso host; cache/noindex delle quattro famiglie di URL con token e policy no-referrer.
- [x] API date impossibili: 400; esclusione del solo appuntamento/evento modificato senza nascondere altre occupazioni.
- [x] PayPal assente dalle nuove scelte e rifiutato lato server anche con link legacy configurati; bonifico e conferma manuale verificati nei test locali.
- [x] Test JavaScript, pytest, migrazioni pertinenti e `git diff --check`; sette test PostgreSQL opt-in superati su cluster UTF-8 usa-e-getta.
- [x] Nomi nell'agenda settimanale corretti localmente: 42 schede con durate da 15 a 240 minuti, riga del nome interamente visibile a 1440×900 e 390×844; dettaglio completo accessibile da tastiera. Da ricontrollare sul servizio dopo il deploy.
- Concorrenza PostgreSQL: prova eseguita, doppia occupazione riprodotta in 9/9 casi forzati; **rischio accettato e correzione rinviata dopo la pubblicazione** per D-125. Non è un gate pre-lancio e non è un test superato; vedi [resoconto](TEST_AUTONOMI_2026-10-20.md).

## 2. Riconciliazione e deploy privato

Seguire [OPERATIONS.md](OPERATIONS.md#paz-a3a4--preflight-e-cutover-diretto-sul-database-render-vuoto). Sul servizio autorizzato:

- [ ] Registrare commit live/candidato, revisione Alembic, stato del servizio e configurazione non segreta; mantenere Basic Auth/noindex e auto-deploy disattivato.
- [ ] **Prima di qualunque migrazione del primo cutover**, eseguire `python patient_cutover_preflight.py --allow-applied`.
- [ ] Se schema legacy con dati: fermarsi e decidere la preservazione; niente backfill automatico o cancellazioni per aggirare il gate.
- [ ] Se `cutover_gia_applicato`: non richiedere un DB vuoto o un nuovo backfill; inventario aggregato separato se serve.
- [ ] Con gate valido e deploy autorizzato: `DISABLE_SCHEDULER=true flask --app app db upgrade`, poi `db check`, `bootstrap-admin` quando previsto e `validate-config`.
- [ ] Confermare `/healthz`, log e smoke Pazienti 2.0: scheda, recapiti, pratiche v2, Calendar manuale, consensi/audit, archiviate in sola lettura.
- [ ] Verificare sessione scaduta, logout → Indietro → nuova richiesta protetta, tastiera e touch.

## 3. Dati e flussi essenziali

- [ ] Se esistono dati da preservare, verificare PITR, backup cifrato, retention e restore su destinazione isolata prima di interventi rischiosi. Con DB davvero vuoto, registrare conteggi e rollback tecnico; attivare la protezione prima del primo dato reale.
- [ ] Inventariare i sintetici, distinguere i reali, preparare dry-run e rimuovere solo con autorizzazione e rollback possibile.
- [ ] Prestazioni: richiesta, notifica, durata manuale, conferma, spostamento e annullamento.
- [ ] Corsi/nascita: singolo/coppia, capienza e lista d'attesa, conferma, token/CSRF, comunicazioni e consensi.
- [ ] Sonno: call, proposta, condizioni/avvio anticipato, bonifico, conferma manuale, questionario e annullamenti.
- [ ] SMTP/Calendar: salvataggio locale anche al guasto, primo errore registrato, avvisi e recovery senza duplicati.
- [ ] 390×844 e 1440×900: navigazione, form, focus, contrasto, messaggi, logo admin e principali stati popolati usabili. Rifiniture non bloccanti nel backlog P1.
- [ ] Contenuti pubblicati autorizzati; analytics non configurati inattivi e nessun tracciamento senza consenso.

## 4. GO e dominio

- [ ] GO esplicito sulla candidata e piano di ritorno applicativo compatibile con i dati A4.
- [ ] Impostare intenzionalmente `APP_ENV=production` e `PUBLIC_BASE_URL=https://scstudioinfermieristico.it`; rimuovere protezione staging soltanto nel cutover concordato.
- [ ] DNS apex/`www` secondo pannello Render, HTTPS, redirect canonici, cookie sicuri, URL email, Open Graph e indicizzabilità delle sole pagine pubbliche.
- [ ] Mittente email e SPF/DKIM/DMARC verificati; smoke sul dominio e monitoraggio di errori, invii, Calendar e database.
- [ ] Campagna e PayPal non vengono attivati da questo GO.

## Evidenze della candidata

La patch originale PR #16 ha CI verde con 468 Python, 7 PostgreSQL saltati e 54 JavaScript. Questa evidenza precede gli adattamenti locali del 20 ottobre; riportare qui gli esiti aggiornati dopo l'esecuzione, senza dati personali o segreti.

Verifica locale del 20 ottobre 2026 sulla candidata aggiornata:

- Suite completa: **472 passed, 7 skipped**; i sette skip PostgreSQL sono stati poi eseguiti separatamente: **7 passed** su PostgreSQL 18.4 UTF-8, cluster temporaneo con socket isolato.
- JavaScript: **54 passed**; `git diff --check` superato e link locali dei 33 documenti Markdown verificati senza destinazioni mancanti.
- Chrome headless, SQLite in memoria e sole identità sintetiche: proposta privata con zero opzioni PayPal e bonifico selezionato, admin e logout a 1440×900/390×844, nessun overflow globale o errore JavaScript; logo leggibile e pulsante Esci con target minimo 44×44 px.
- Logout → Indietro e nuova richiesta `/admin`: login richiesto in entrambi i casi.
- Queste prove non includono richieste simultanee prestazione/call, stati admin densamente popolati, pagamenti/invii reali, stato Render o dominio pubblico. I relativi gate restano aperti sopra.

### Prove autonome successive e pulizia Render

Il [resoconto del 20 ottobre](TEST_AUTONOMI_2026-10-20.md) integra le evidenze precedenti: 472 Python superati, sette PostgreSQL opt-in superati separatamente e 54 JavaScript superati sulla candidata `016f93d`; concorrenza e agenda popolata avevano evidenziato due difetti. La concorrenza è rinviata al post-lancio per D-125, senza attestare la riuscita della prova. Il difetto dei nomi nell'agenda è stato poi corretto e verificato localmente: suite Python 472 passed, 7 skipped; JavaScript 55 passed con la nuova regressione CSS; controllo browser delle 42 schede superato alle due dimensioni.

Pulizia autorizzata e verificata nel solo database del servizio Render di produzione: eliminati otto appuntamenti test del 2027, due corsi test e sei iscrizioni esplicitamente confermate dal committente. Preservati i tre altri appuntamenti del 2027, anagrafiche e storico; aggiunte sedici voci di audit. Nessuna operazione Calendar o email, nessun deploy. Questa pulizia circoscritta non certifica l'assenza di qualsiasi altro dato sintetico.

Per D-124 gli agenti non devono modificare Calendar reale: i test locali usano simulazioni; le prove di scrittura esterne sopra elencate restano non eseguite e non autorizzate.
