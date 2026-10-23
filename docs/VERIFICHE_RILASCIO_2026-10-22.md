# Evidenze di rilascio — 22 ottobre 2026

Questo resoconto distingue ciò che è stato provato da ciò che è riferito dal committente. Le priorità sono soltanto in [ROADMAP.md](ROADMAP.md); le procedure in [OPERATIONS.md](OPERATIONS.md). Nessun GO pubblico è stato dato.

## Codice, schema e test

| Evidenza | Fonte e perimetro | Limite |
|---|---|---|
| `3fe6033` su `origin/main` | Commit e push verificati dall'agente; manual deploy successivamente confermato dal committente | Il collegamento DNS non certifica il commit in esecuzione: il controllo del ricontatto è la verifica applicativa diretta post-deploy |
| Ricontatto minimo sul servizio Render | Osservato dopo il deploy sulla pagina accompagnamento alla nascita: action `/iscrizione-corsi/interesse`, soli nome, telefono, email, tematica, note e privacy | Nessun invio live; non prova persistenza o notifica reali |
| Età del bambino obbligatoria nella call | Conferma esplicita del committente, D-130; modulo mantenuto invariato | Nessun limite di ammissione in base all'età |
| `e8b1c4d7a902`, `cutover_gia_applicato` | Output del preflight Render fornito dal committente sulla candidata precedente; nessuna nuova migrazione in `3fe6033` | Non è un inventario dei dati e non richiede database vuoto/backfill |
| `validate-config` staging e production riusciti | Output Render fornito dal committente; production provata con override temporaneo e scheduler disabilitato | Non significa ambiente pubblico o configurazione production applicata stabilmente |
| Python 504 passed, 12 skipped; JavaScript 55 passed; diff senza errori | Suite locale prima del commit, worktree comprensivo dei test backup non ancora committati; include quattro nuove regressioni ricontatto | Non è CI del solo commit; gli skip non sono test superati; nessuna scrittura Calendar reale |
| Quattro pagine corso a 1440×900 e 390×844 | Anteprima locale isolata, modulo minimo con tematica preselezionata; un h1, nessun overflow globale | Le iscrizioni con date disponibili restano coperte dai test locali, non da nuovi invii live |
| Navigazione pubblica Render desktop/mobile | Homepage, corsi, sonno, prestazioni, aziende, privacy; menu mobile e selettore prestazioni usabili, nessun errore console osservato nei controlli | Non audit completo di accessibilità, non prova di tutti i link e non collaudo admin live |

## Dominio ancora privato — D-131

- OVH: screenshot della zona DNS con apex A `216.24.57.1` e `www` CNAME verso `sc-studio-infermieristico-production.onrender.com.`. Record della posta conservati nello screenshot; nessuna attestazione nuova di consegna SMTP/SPF/DKIM/DMARC.
- Render: verifica DNS confermata dal committente. Certificato apex `Certificate issued`; ultimo stato esplicito di `www` `Certificate pending`, da ricontrollare.
- Il committente ha impostato `PUBLIC_BASE_URL=https://scstudioinfermieristico.it`, mantenuto `APP_ENV=staging` e `STAGING_AUTH_*`, poi confermato «tutto funzionante» sul dominio con password. È una conferma d'uso, non una nuova lettura diretta di tutte le variabili/header.
- Non sono stati autorizzati apertura anonima, `APP_ENV=production`, rimozione della Basic Auth, indicizzazione, campagne o analytics. Il login admin deve restare distinto e protetto anche al lancio.

## Backup e dati

Backup age indipendenti su memoria interna Mac e Windows, reti separate, monitor distinti a 72 ore ed email tecnica ricevuta. Windows: dump cifrato, verifica, restore isolato con 28 tabelle riuscito e database di prova rimosso; attività pianificata e monitor provati con codice 0. Mac: primo archivio reale e controllo riusciti, job e monitor attivi; restore sintetico autonomo riuscito. Dettagli e limiti in [OPERATIONS.md](OPERATIONS.md#backup-e-ripristino-postgresql).

Non sono attestati continuità delle scadenze ordinarie delle 21:00/22:00, recupero fisico dopo stop/riavvio, restore del nuovo archivio reale Mac o test reale di assenza segnali per 72 ore. I due backup online non dimostrano immutabilità né due sedi fisiche distinte.

La pulizia test Render del 20 ottobre resta circoscritta ai bersagli autorizzati descritti nel [resoconto storico](TEST_AUTONOMI_2026-10-20.md). Non certifica assenza di qualsiasi dato sintetico. Nessun dato nominativo o segreto è riportato qui.

## Non concluso / non eseguito

- Certificato e redirect `www`, verifica HTTPS/HTTP e noindex sul dominio definitivo in sessione anonima.
- Admin Pazienti 2.0 popolato sul dominio e ciclo di sessione/logout. Attenzione: alcune route GET admin possono riconciliare dati e non sono automaticamente read-only.
- Nuovi invii live e comunicazioni dei flussi prestazioni, corsi, nascita e sonno; bonifico/questionario con token reali. Test locali e collaudi storici non li sostituiscono.
- Scritture Calendar reali vietate agli agenti, anche per prova o pulizia: usare simulazioni; un eventuale collaudo gestito dal committente richiede una decisione separata e non viene presunto autorizzato.
- Concorrenza richieste: difetto riprodotto, rischio accettato per il primo lancio e correzione P1 post-pubblicazione (D-125), non test superato.
- GO pubblico, configurazione production stabile e controlli successivi al lancio.

Questa revisione modifica soltanto documenti. Non avvia backup, task, connessioni private, email, migrazioni, deploy, DNS o operazioni Calendar.
