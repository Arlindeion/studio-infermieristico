# Roadmap di sviluppo e pubblicazione

Revisione: **22 ottobre 2026**. Fonte unica delle priorità; registro delle scelte in [DECISIONS.md](DECISIONS.md), procedure in [OPERATIONS.md](OPERATIONS.md), prove e limiti in [VERIFICHE_RILASCIO_2026-10-22.md](VERIFICHE_RILASCIO_2026-10-22.md).

## Stato attuale: vetrina pubblicata e verificata sul dominio

- 17 novembre 2026, D-138: il committente conferma l'apertura pubblica e richiede una vetrina parallela senza prenotazioni di corsi, prestazioni o call sonno. Implementata localmente con raccolta interesse via email; versione completa conservata tramite configurazione. Deploy manuale autorizzato dal committente fino al punto 2 ed eseguito: commit `a502765`, Render Live il 17 novembre alle 21:30 circa (Europe/Rome). Vetrina osservata sul dominio; parametro del punto 3 non modificato, modalità attiva tramite default production. Riscontri HTTP e limiti in OPERATIONS.md. Procedura in [OPERATIONS.md](OPERATIONS.md#vetrina-pubblica-parallela--17-novembre-2026-d-138). Il riepilogo del 22 ottobre sottostante resta storico, non certifica la configurazione online attuale.

- Aggiornamento locale D-137, 14 novembre 2026: semplificata la raccolta delle dichiarazioni in disostruzione. Una sola spunta obbligatoria per condizioni e natura del corso; privacy come nota con link. Su scelta del committente resta una spunta facoltativa distinta per futuri laboratori e l'età del bambino, utilizzata solo con opt-in e rimovibile alla revoca. Prezzi e percorso Nexi invariati; nessuna migrazione. Verificato in locale; incluso nel deploy D-138 del 17 novembre.
- D-136, 14 novembre 2026: modalità Nexi di prova del corso attivata sullo staging Render su ordine del committente («configura»). Deploy `36ac840` Live, pulsante Nexi verificato sul dominio; password staging e autenticazione della notifica preservate. Nessuna nuova iscrizione o email creata dagli agenti nella verifica. Iscrizioni ed eventuali email di prova seguono database e configurazione dello staging; nessun pagamento reale o apertura pubblica. [Riscontro e istruzioni](NEXI_SANDBOX.md#collaudo-del-corso-sullo-staging-render-d-136).
- Aggiornamento locale D-135, 14 novembre 2026: nuovo percorso disostruzione con acconto 50% (17/30 €), conferma automatica dopo verifica Nexi, email e nominativi nella scheda corso. Condizioni aggiornate con preavviso sonno, perdita dell’acconto per assenza senza preavviso valido e quota singola 34 € se partecipa una sola persona della coppia (saldo 4 €). Nessuna attivazione reale o deploy implicito; [procedura e verifiche](NEXI_SANDBOX.md).

- Aggiornamento locale del 14 novembre 2026: Nexi sandbox esteso a disostruzione pediatrica e tagli sicuri, singolo 34 € e coppia 60 € (D-134). Sono preservate capienza, lista d'attesa e conferma manuale del posto; nessuna attivazione online. Evidenze in [NEXI_SANDBOX.md](NEXI_SANDBOX.md).
- Aggiornamento locale del 13 novembre 2026: collaudo Nexi HPP su copia temporanea isolata (D-133) completato per desktop/mobile, Visa, 3DS, ritorno e notifiche HTTPS. Anomalia su due Mastercard di test da chiarire con Nexi; evidenze e limiti in [NEXI_SANDBOX.md](NEXI_SANDBOX.md). Non cambia lo stato del dominio, non attiva Nexi sul sito operativo e non riapre PayPal.

- Il commit `3fe6033` è su `origin/main`; manual deploy confermato dal committente. Il ricontatto minimo è stato osservato sul servizio Render dopo il deploy.
- `https://scstudioinfermieristico.it` funziona e richiede ancora la password, secondo conferma del committente. `APP_ENV=staging`, `STAGING_AUTH_*` conservate e `PUBLIC_BASE_URL` sul dominio definitivo: il collegamento del dominio non è un GO pubblico.
- DNS OVH configurati e domini verificati su Render. Certificato apex emesso; ultimo stato esplicito di `www`: pending. Non dichiararlo risolto sulla sola conferma generale di funzionamento.
- Schema `e8b1c4d7a902`, preflight `cutover_gia_applicato` e validazione staging riferiti dal committente; validazione production riuscita con override temporaneo, non attivazione della produzione.
- Backup age e monitor a 72 ore installati su Mac e Windows; restore reale Windows riuscito. Riscontro del 13 novembre: Mac caricato, ultimo backup e monitor riusciti il 12 novembre alle 22:02 italiane; Windows non riverificato dopo le evidenze del 22 ottobre. Dettagli in [OPERATIONS.md](OPERATIONS.md#riscontro-locale-del-13-novembre-2026). Continuità, recupero fisico dopo stop/riavvio e restore del nuovo archivio reale Mac restano da documentare.
- PayPal sospeso fino a nuovo ordine. Sonno: bonifico e conferma manuale. Età in mesi obbligatoria, senza limite di ammissione. Ricontatti senza date: modulo minimo, non iscrizione.
- Non sono certificati tutti i flussi live, l'admin popolato sul nuovo dominio o il GO. Gli agenti non devono modificare Calendar reale (D-124).

## Come leggere il piano

P0 indica un requisito essenziale prima del pubblico; P1 uno sviluppo prioritario dopo il lancio, salvo un nuovo difetto effettivamente bloccante; P2 un miglioramento da valutare sui bisogni reali. Le attività future sono **proposte di lavoro**, non autorizzazioni a spesa, invii, scritture live, nuove integrazioni o deploy.

La gerarchia resta corsi → sonno → prestazioni. Non avviare redesign o nuove funzioni per ritardare il lancio. Il collegamento privato del dominio è completato secondo D-131; la data di apertura resta scelta del committente.

## Fase A — completare il collaudo sul dominio protetto

| ID | Priorità / stato | Prossimo passo | Criterio di chiusura / responsabilità |
|---|---|---|---|
| A1 | P0, da verificare | Chiudere certificato `www`, HTTPS e redirect verso apex | Entrambi i certificati emessi; `http` → `https`, `www` → apex senza cicli. Confrontare stato Render e navigazione effettiva. |
| A2 | P0, parzialmente verificato | Registrare configurazione e protezioni del dominio | Senza credenziali accesso negato; con password navigazione corretta; `/healthz` sano, `robots.txt` bloccante, noindex globale. Canonical/URL generati sul dominio, nessun segreto nel resoconto. |
| A3 | P0, da completare | Collaudare admin Pazienti 2.0 e sessioni sul dominio | Scheda/recapiti/pratiche, audit, consensi, archiviate in sola lettura, logout/Indietro, tastiera e mobile. Le route GET admin possono riconciliare dati: non aprirle assumendo assenza di scritture; preparare una prova sicura con il committente. |
| A4 | P0, parzialmente verificato | Chiudere flussi essenziali, non aggiungerne altri | Prestazioni, corsi singolo/coppia/capienza/attesa, open day e modulo nascita privato; sonno call → proposta → bonifico → questionario. I test locali sono superati; invii reali, email e stati live non vengono dichiarati collaudati senza prova. |
| A5 | P0 operativo, avviato | Completare evidenza di backup e recuperabilità | Verificare copie recenti e monitor distinti, esecuzioni ordinarie e restore isolato. Restore Windows attestato; nuovo archivio Mac e recupero fisico ancora da collaudare. Un controllo positivo non prova la continuità futura. |
| A6 | P0, da riconfermare | Confermare contenuti, posta e gestione richieste | Autorizzazioni dei materiali pubblicati e revisione professionale/legale già attestata nello storico; verificare mittente, recapito notifiche e SPF/DKIM/DMARC effettivi senza alterare i record della posta. Bonifico utilizzabile senza pubblicarne i dati nella documentazione. |

I test che richiedono scritture su Calendar reale restano sospesi. Per gli altri collaudi esterni servono piano, destinatari controllati e autorizzazione pertinente; dove il divieto impedisce la prova, registrare il limite e chiedere la decisione del committente. Non inventare test superati né aggirare il divieto.

## Fase B — apertura al pubblico, soltanto nel giorno scelto

| ID | Stato | Azione e criterio di uscita |
|---|---|---|
| B1 | Non autorizzato | GO esplicito sulla candidata, esiti della fase A e rischi residui. Preparare ritorno applicativo compatibile con lo schema: nessun downgrade o cancellazione dati automatici. |
| B2 | Da eseguire dopo GO | `APP_ENV=production`, mantenere `PUBLIC_BASE_URL=https://scstudioinfermieristico.it`, rimuovere `STAGING_AUTH_*` nel cutover concordato e ridistribuire. Non eliminare la Basic Auth restando staging. Login amministratore e protezioni delle route private restano attivi. |
| B3 | Da eseguire dopo B2 | Verificare accesso anonimo pubblico, admin protetto, cookie sicuri, canonical/OG/sitemap e URL email; indicizzabilità delle sole pagine pubbliche, nessuna pagina/token privato nei motori. |
| B4 | Da eseguire dopo B3 | Solo dopo HTTPS e canonical corretti valutare disattivazione del sottodominio Render, aggiornando eventuali riferimenti operativi. Monitorare errori, richieste, email e backup nelle prime 24–72 ore; nessuna attivazione automatica di analytics, campagna o PayPal. |

La checklist eseguibile è [PRE_GO_LIVE_CHECKLIST.md](PRE_GO_LIVE_CHECKLIST.md). La sola rimozione di una password non completa il rilascio. Il calendario di lancio non è imposto da questa roadmap.

## Fase C — P1 dopo la prima pubblicazione e stabilizzazione

Ordine proposto: integrità → gestione operativa → ottimizzazione della conversione → campagna.

| ID | Ambito | Sviluppo proposto | Verifica di completamento |
|---|---|---|---|
| C1 | Integrità | Protezione atomica condivisa tra prenotazioni prestazione e call sonno | Le tre combinazioni concorrenti passano su PostgreSQL, nessuna doppia occupazione né perdita della richiesta. Rischio accettato per il lancio in D-125; non è risolto e non è più un P0. |
| C2 | Operatività | Rendere ripetibili controlli backup/restore e aggiornamento IP autorizzati | Checklist mensile di restore, responsabilità assegnata, spazio/retention controllati; nessuna apertura `0.0.0.0/0`. Valutare separatamente una copia offline/immutabile, senza acquisti automatici. |
| C3 | Gestionale | Ridurre attriti reali di ricerca, filtri, stati e attività di ricontatto | Partire da casi osservati, garantire audit e persistenza prima delle notifiche; non ampliare cartella clinica o ruoli. |
| C4 | UI e accessibilità | Rifinire messaggi di errore/esito, focus, target touch, densità admin e coerenza delle CTA | Nessun passo ambiguo tra interesse e iscrizione; desktop 1440×900 e mobile 390×844, tastiera e contrasto verificati. Riutilizzare i token e i componenti del brand. |
| C5 | Foto e prestazioni | Ottimizzare peso/dimensioni immagini, ritagli mobile, caricamento e stabilità del layout | Confronto prima/dopo su pagine principali; preservare fotografie reali e qualità, niente stock o redesign generalizzato. |
| C6 | SEO e presentazione | Rifinire anteprime social, titoli, descrizioni e dati strutturati | URL canonici e dati coerenti per pagina; nessuna indicizzazione admin/token. Attivare gli strumenti di indicizzazione soltanto dopo il pubblico. |
| C7 | Misurazione e funnel | Misurare corsi, call, prestazioni e aziende, poi correggere i punti di abbandono | Piano eventi con consenso verificato, baseline definita, nessun dato sanitario negli eventi. L'eventuale attivazione di GA4/Meta richiede autorizzazione separata. |
| C8 | Campagna sonno | Preparare un test limitato con capacità operativa sostenibile | Dominio pubblico stabile, misurazione consentita, creatività e budget riconfermati; nessuna spesa o pubblicazione automatica. Testimonianze solo reali e autorizzate. |
| C9 | Processo tecnico | Revisione delle modifiche e protezione del branch; limiti distribuiti prima di scalare | Verificare prima di aumentare worker/istanze; nessuna nuova infrastruttura senza necessità osservata e costo autorizzato. |

## Fase D — P2, solo dopo verifica del bisogno

- Nuove funzioni Pazienti, cartella infermieristica, allegati clinici, ruoli/multiaccount: analisi dedicata di privacy, accessi, backup e audit prima di progettare.
- Automazioni di follow-up e promemoria: prima capire il carico manuale reale, poi definire destinatari, consensi e gestione errori.
- Nuove landing, materiali social e ampliamenti dei servizi: valutare domanda e capacità, conservare la gerarchia commerciale.
- Evoluzione estetica più ampia: solo su problemi osservati, senza cambiare implicitamente prezzi, flussi o regole di capienza.
- Eventuali rateizzazioni e pagamenti aggiuntivi: decisione separata, non inclusa nel percorso minimo.

**PayPal rimane sospeso fino a nuovo ordine**, anche dopo il completamento delle fasi A–C. Nessuna data automatica di ripresa. Le condizioni o proposte storiche non ne attestano l'attivazione.

## Storico e regole di avanzamento

I vecchi step 1–20 e la riconciliazione PR #16 restano riferimenti storici nei documenti datati e nella storia Git, non una seconda coda di priorità. D-123 resta la priorità di lancio; D-124 vieta scritture Calendar reali; D-125 accetta temporaneamente la concorrenza; D-128–D-129 descrivono backup e monitor; D-130 fissa ricontatto ed età sonno; D-131 distingue dominio privato e pubblico; D-132 disciplina questa roadmap.

Una voce cambia stato soltanto con evidenza datata e perimetro esplicito. Conferma del committente, verifica diretta, test locale e CI non sono equivalenti. Aggiornare la fonte competente e collegarla dagli altri Markdown, senza riscrivere i documenti storici come attestazioni correnti.
