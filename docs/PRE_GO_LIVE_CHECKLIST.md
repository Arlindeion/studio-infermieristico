# Checklist di pubblicazione sul dominio

Aggiornamento 22 ottobre 2026: **dominio funzionante con password, nessun GO pubblico** (D-131). Stato e ordine del lavoro in [ROADMAP.md](ROADMAP.md); fonti delle prove in [VERIFICHE_RILASCIO_2026-10-22.md](VERIFICHE_RILASCIO_2026-10-22.md). Le caselle aperte non cancellano le evidenze storiche: indicano controlli non interamente documentati sulla candidata e sul dominio correnti.

Priorità del 20 ottobre 2026: [roadmap corrente](ROADMAP.md), decisione D-123. PayPal è sospeso; il flusso sonno usa il bonifico con conferma manuale. Campagna, nuove funzioni e redesign non sono gate della prima pubblicazione.

## 1. Candidata locale

- [x] Candidata `3fe6033`, commit e push verificati; manual deploy confermato. Test locali ricontatto/sonno e grafica desktop/mobile eseguiti; perimetro del worktree e skip nel resoconto del 22 ottobre. La CI della PR #16 non attesta queste modifiche.
- [x] CSRF: proposta orario, lista d'attesa e logout POST; rifiuto di token assenti, errati e non ASCII senza errori 500.
- [x] Redirect login locali/sullo stesso host; cache/noindex delle quattro famiglie di URL con token e policy no-referrer.
- [x] API date impossibili: 400; esclusione del solo appuntamento/evento modificato senza nascondere altre occupazioni.
- [x] PayPal assente dalle nuove scelte e rifiutato lato server anche con link legacy configurati; bonifico e conferma manuale verificati nei test locali.
- [x] Test JavaScript, pytest, migrazioni pertinenti e `git diff --check`; sette test PostgreSQL opt-in superati su cluster UTF-8 usa-e-getta.
- [x] Nomi nell'agenda settimanale corretti localmente: 42 schede con durate da 15 a 240 minuti, riga del nome interamente visibile a 1440×900 e 390×844; dettaglio completo accessibile da tastiera. Da ricontrollare sul servizio dopo il deploy.
- Concorrenza PostgreSQL: prova eseguita, doppia occupazione riprodotta in 9/9 casi forzati; **rischio accettato e correzione rinviata dopo la pubblicazione** per D-125. Non è un gate pre-lancio e non è un test superato; vedi [resoconto](TEST_AUTONOMI_2026-10-20.md).

## 2. Riconciliazione e deploy privato

Seguire [OPERATIONS.md](OPERATIONS.md#paz-a3a4--preflight-e-cutover-diretto-sul-database-render-vuoto). Sul servizio autorizzato:

- [x] Commit candidato e manual deploy `3fe6033` registrati; ricontatto minimo osservato sul servizio dopo deploy. Basic Auth mantenuta sul dominio secondo conferma del committente.
- [x] Registrato preflight `cutover_gia_applicato`, revisione `e8b1c4d7a902` e validazioni staging/production riferite dal committente prima dell'ultima correzione senza migrazioni. Production validata con override temporaneo, non attivata stabilmente.
- [ ] Riconfermare health, log, header noindex, runtime non segreto e auto-deploy/Sync dal pannello prima del GO; non leggere o registrare segreti.
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

- [x] Collegamento privato del dominio autorizzato: DNS OVH apex/`www` configurati e verificati su Render, record posta preservati nello screenshot, certificato apex emesso; `PUBLIC_BASE_URL` sul dominio e funzionamento con password confermati dal committente.
- [ ] Confermare certificato `www` emesso e redirect HTTPS/`www` → apex; ultimo stato esplicito ancora pending. Verificare accesso anonimo bloccato, canonical, robots/noindex sul dominio protetto.

- [ ] GO esplicito sulla candidata e piano di ritorno applicativo compatibile con i dati A4.
- [ ] Solo dopo nuovo GO: impostare intenzionalmente `APP_ENV=production`, mantenere `PUBLIC_BASE_URL=https://scstudioinfermieristico.it` e rimuovere le sole credenziali `STAGING_AUTH_*` nel cutover concordato; login admin sempre protetto. Oggi resta staging con password.
- [ ] DNS apex/`www` secondo pannello Render, HTTPS, redirect canonici, cookie sicuri, URL email, Open Graph e indicizzabilità delle sole pagine pubbliche.
- [ ] Mittente email e SPF/DKIM/DMARC verificati; smoke sul dominio e monitoraggio di errori, invii, Calendar e database.
- [ ] Campagna e PayPal non vengono attivati da questo GO.

## Evidenze della candidata

### Evidenze correnti — 22 ottobre 2026

Il [resoconto corrente](VERIFICHE_RILASCIO_2026-10-22.md) registra `3fe6033`, quattro regressioni ricontatto e la conferma dell'età obbligatoria nella call. Esito locale del worktree (con test backup non ancora committati): **504 passed, 12 skipped**, **55 JavaScript passed**, `git diff --check` superato. Controllo delle quattro pagine corso a 1440×900 e 390×844 senza overflow. Nessun nuovo invio live né collaudo completo admin sul dominio.

Backup e monitor Mac/Windows attivi; restore Windows isolato con 28 tabelle riuscito secondo output del committente. Restano evidenze delle scadenze ordinarie, recupero fisico stop/riavvio e restore dell'archivio reale Mac, come in [OPERATIONS.md](OPERATIONS.md#backup-e-ripristino-postgresql).

### Evidenze storiche precedenti alla candidata corrente

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
