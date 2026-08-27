# Operatività tecnica

Revisione documentale: 13 agosto 2026. Le ultime evidenze esterne registrate in questo documento risalgono al 30 luglio 2026 e non dimostrano da sole lo stato corrente dei pannelli.

## Architettura

- Applicazione Flask monolitica in `app.py`.
- Rendering server-side con Jinja2.
- SQLAlchemy ORM; SQLite locale e PostgreSQL in produzione.
- JavaScript vanilla esternalizzato per rispettare la Content Security Policy.
- Flask-Login per l'area admin.
- Flask-Mail per le notifiche.
- Flask-Limiter per i limiti di richiesta.
- Flask-Talisman per gli header di sicurezza.
- APScheduler per promemoria, scadenze e riconciliazione oraria.
- Google Calendar come collante con Arzamed.

Non introdurre framework frontend, SQL grezzo o dipendenze non necessarie.
- Richieste organizzative in `richiesta_azienda`, separate da appuntamenti e iscrizioni individuali.

Il redesign corrente resta interamente nel rendering Flask/Jinja e negli asset
CSS e JavaScript statici. Snap della homepage, movimento delle pagine interne,
feed Behold e transizioni orizzontali non richiedono un processo applicativo,
un servizio 3D o un piano Render aggiuntivo. L'anteprima della transizione
richiede una seconda risposta HTML per i clic interni idonei, con un incremento
contenuto di richieste e banda; se non è pronta entro il timeout, il link apre
comunque la pagina normalmente.

## Ambienti

`FLASK_ENV` seleziona `development`, `production` o `testing` da `config.py`.

- Development: SQLite predefinito, debug attivo, cookie utilizzabili su HTTP locale.
- Production: debug disattivato e cookie di sessione `Secure`.
- Testing: database SQLite in memoria, email soppresse, Calendar e Analytics disattivati.

### Architettura Render approvata

| Ambiente | Applicazione | Database | Indirizzo | Accesso |
|---|---|---|---|---|
| Staging iniziale | Render Web Service Free, Francoforte | Render PostgreSQL Free, Francoforte | sottodominio `onrender.com` | Basic Auth applicativa e `noindex` globale |
| Produzione | Render Web Service Starter o superiore, Francoforte | Render PostgreSQL Basic-256mb o superiore, Francoforte | `scstudioinfermieristico.it` | pubblico dopo il gate pre-lancio |

Staging e produzione usano risorse separate. Il database gratuito non viene
promosso, copiato o collegato alla produzione: il database pagato nasce vuoto e
riceve soltanto dati creati durante i collaudi controllati e, dopo il cutover,
dati reali. Questa separazione evita che dati fittizi, credenziali o
configurazioni dello staging entrino nell'ambiente pubblico.

Render gestisce e rinnova HTTPS. Il filesystem del servizio è effimero e non
contiene dati persistenti; ogni dato applicativo va in PostgreSQL. Lo staging
usa esclusivamente dati fittizi. Il database gratuito scade 30 giorni dopo la
creazione, non dispone di backup e deve essere aggiornato o sostituito prima
della scadenza. Web Service e database restano nella stessa regione.

Il repository contiene `render.yaml` con auto-deploy disattivato. I deploy
partono intenzionalmente da un commit identificabile. `SECRET_KEY` è generata da
Render; `DATABASE_URL` proviene dal database associato. Le variabili con
`sync: false` vanno compilate nel pannello senza inserirne il valore nel file.
Lo staging segue `main` e `autoDeployTrigger` resta `off`: i nuovi commit non
avviano deploy automatici. Una sincronizzazione del Blueprint è però una
modifica di configurazione e può avviare il deploy dei servizi interessati
anche con l'auto-deploy spento. Va quindi trattata come un'operazione capace di
pubblicare codice: prima di approvarla verificare il commit proposto e
monitorare subito la cronologia deploy, annullando l'esecuzione se lo scopo era
soltanto allineare la configurazione. Ogni deploy intenzionale continua a
partire da un commit già verificato.

Il 30 luglio 2026 il Blueprint dello staging è stato disconnesso per revocare
un Sync Hook considerato non più affidabile. La disconnessione non ha eliminato
né modificato Web Service e PostgreSQL: il servizio resta collegato a `main`,
con deploy manuali. Nella stessa data il database è stato portato alla revisione
Alembic `4d8b2c7a91e6`; un successivo tentativo di avvio del vecchio commit
`8a4ad84`, che non conteneva quella revisione, è fallito senza modificare i dati.
Il deploy manuale del `main` verificato `148ec36` ha riallineato codice e schema:
migrazione, bootstrap, Gunicorn e health check sono riusciti e `/healthz` ha
risposto `200`. Non eseguire rollback a commit che non contengono la revisione
registrata nel database. Prima di ricollegare `render.yaml` occorre scegliere
una finestra di deploy controllata, verificare il piano proposto e considerare
la prima sincronizzazione capace di avviare un deploy.

All'avvio Render esegue nell'ordine `flask db upgrade`, il comando sicuro
`bootstrap-admin` e infine Gunicorn. I comandi preparatori disabilitano lo
scheduler; il processo Gunicorn lo avvia una sola volta perché usa un worker.

`render.production.yaml` è il file del Blueprint
`sc-studio-infermieristico-production`, creato il 23 agosto 2026 dopo l'ordine
di spesa per 13,30 USD/mese più eventuali imposte. Gestisce il Web Service
Starter e il PostgreSQL Basic-256mb separati dallo staging gratuito. Auto Sync
è impostato su `No`: ogni futura sincronizzazione resta un'operazione capace di
modificare la configurazione e avviare un deploy, quindi richiede un gate
intenzionale.

Il file mantiene intenzionalmente sicura la preproduzione privata:

- usa `main`, da portare sempre esattamente al commit approvato e verificato;
- crea Web Service Starter e PostgreSQL Basic-256mb separati in Francoforte;
- fissa il disco iniziale a 1 GB e disabilita l'autoscaling per evitare aumenti
  automatici di costo;
- colloca le risorse in un ambiente Render protetto e con rete privata isolata;
- blocca ogni connessione PostgreSQL esterna con `ipAllowList: []`;
- mantiene `APP_ENV=staging`, Basic Auth, `noindex`, invii email soppressi e
  integrazioni reali disattivate;
- mantiene auto-deploy e preview disattivati;
- non collega il dominio e conserva il sottodominio Render soltanto per il
  collaudo privato;
- usa un pre-deploy separato per migrazioni e verifica dell'admin esistente,
  lasciando a Gunicorn il solo avvio dell'applicazione.

Il primo deploy del commit `ac17eaf` e il deploy successivo alla rimozione dei
segreti `ADMIN_BOOTSTRAP_*` sono risultati `Live`. Il controllo del 23 agosto ha
confermato `APP_ENV=staging`, root `401`, `/healthz` `200`, `robots.txt` con
`Disallow: /`, intestazioni CSP, HSTS, anti-framing, `nosniff` e
`X-Robots-Tag`, database alla revisione `d91e6b4f2a30`, `flask db check` senza
nuove operazioni e `validate-config` riuscito.

Il JSON Google non è rappresentato nel Blueprint. Prima del collaudo reale va
caricato direttamente come secret file con nome
`google-calendar-service-account.json`; Render lo monta in
`/etc/secrets/google-calendar-service-account.json`. Nessun valore segreto va
inserito nel repository.

Al controllo del 23 agosto il secret file non era ancora presente. I log live
mostravano tentativi di autenticazione Calendar riferiti esclusivamente al file
mancante quando veniva aperta l'agenda; non sono stati osservati indirizzi email
o altri dati personali nei messaggi. Quel rilievo è una fotografia storica:
tra il 24 e il 26 agosto il secret file e la configurazione Zimbra sono stati
attivati intenzionalmente nella preproduzione privata e usati nel collaudo reale
descritto sotto. Con `APP_ENV=staging` e `STAGING_LIVE_INTEGRATIONS=false`
l'app continua a non autenticare, leggere o scrivere su Calendar.

Il 30 luglio 2026 sono stati verificati dal pannello Google il progetto Cloud,
Google Calendar API abilitata, l'identità tecnica dedicata e la relativa chiave.
Il calendario operativo dello studio è condiviso con tale identità usando il
permesso di modifica degli eventi, senza gestione della condivisione; resta non
pubblico. Arzamed usa lo stesso account Google e mostra attivo il modulo di
sincronizzazione esterna. Il file JSON locale è escluso da Git, non tracciato e
leggibile soltanto dal proprietario; il suo contenuto non è stato aperto né
registrato nella documentazione.

### Gate delle risorse di produzione separate

La sequenza seguente è obbligatoria e non può essere anticipata:

1. ottenere un ordine esplicito per generare costi Render;
2. rileggere dal pannello costo totale, metodo di pagamento e piani selezionati;
3. portare `main` al commit verificato senza modificare la storia pubblicata;
4. creare il Blueprint da `render.production.yaml` senza dominio e con
   configurazione privata;
5. inserire i segreti direttamente nel pannello, senza attivare le integrazioni;
6. verificare database vuoto, migrazioni, admin, Basic Auth, `noindex`,
   `/healthz` e assenza di dati reali;
7. ottenere autorizzazioni separate prima di caricare il secret file Google,
   abilitare email reali o consentire scritture Calendar;
8. collaudare i flussi con dati sintetici e rimuovere gli eventi di prova;
9. restringere l'accesso esterno al database alla sola sorgente necessaria per
   il backup cifrato, dopo aver scelto una provenienza IP stabile; non usare
   `0.0.0.0/0`;
10. chiudere tutti i P0 e ottenere un ordine esplicito distinto prima di
    impostare `APP_ENV=production`, collegare DNS/dominio o rendere pubblico il
    servizio.

L'attivazione delle integrazioni in preproduzione richiede una modifica
intenzionale e congiunta di `STAGING_LIVE_INTEGRATIONS=true` e
`MAIL_SUPPRESS_SEND=false`. Il cutover finale richiede invece
`APP_ENV=production`, `PUBLIC_BASE_URL=https://scstudioinfermieristico.it`,
rimozione delle variabili `STAGING_AUTH_*`, collegamento del dominio e, dopo la
verifica dei canonical, disattivazione del sottodominio Render. Questi valori
non sono inclusi nel Blueprint preparatorio per impedire un'apertura
accidentale.

Per il primo deploy dello staging sono obbligatorie:

- `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD`;
- `STAGING_AUTH_USERNAME` e `STAGING_AUTH_PASSWORD`;
- password di almeno 16 caratteri, distinte tra amministratore e accesso allo staging.

Dopo il primo login amministrativo riuscito, rimuovere le due variabili
`ADMIN_BOOTSTRAP_*` e ridistribuire: l'account resta in PostgreSQL. Le variabili
`STAGING_AUTH_*` restano finché l'ambiente è uno staging. Il piano gratuito
blocca SMTP sulle porte 25, 465 e 587: email reali e Calendar vengono collaudati
nelle fasi previste dalla roadmap, non aggirando la limitazione con segreti o
dati reali nello staging gratuito.

Endpoint operativo: `/healthz` verifica anche la connessione al database e resta
escluso sia dalla Basic Auth sia dai limiti globali di Flask-Limiter. Render lo
interroga più volte durante l'avvio e poi periodicamente: applicargli il limite
generale produce falsi `429` e può mettere l'istanza in un ciclo di riavvii.
`/robots.txt` nello staging risponde con `Disallow: /`; ogni risposta include
inoltre `X-Robots-Tag: noindex, nofollow, noarchive`.

### Limiti di richiesta

Flask-Limiter applica per IP un limite aggregato alle richieste dinamiche di
`1000 per hour` e `10000 per day`. Asset statici e `/healthz` sono esclusi: la
navigazione, il caricamento di CSS, JavaScript e immagini e i controlli Render
non devono consumare quote destinate alla protezione dell’applicazione.

Le route pubbliche miste `GET`/`POST` limitano soltanto i POST: `5 per hour` per
la richiesta di call sonno, `10 per hour` per questionario sonno, proposta slot
e lista d’attesa, `5 per minute` per prenotazioni sanitarie, corsi, interesse
corsi, aziende e gruppi, percorso nascita privato e login. Un POST invalido,
compresi errori di validazione o CSRF, conta come tentativo: escluderlo
permetterebbe invii automatici malformati senza limite. L’API GET degli orari
call sonno mantiene inoltre il limite specifico `30 per minute`.

Le risposte `429` includono le intestazioni di rate limiting e `Retry-After`,
mostrano un messaggio italiano e registrano soltanto endpoint, metodo e soglia,
senza IP, token o dati inseriti. `memory://` è adeguato finché Render usa un solo
worker; prima di aumentare worker o istanze occorre passare a uno storage
condiviso, per esempio Redis, e ripetere i test di concorrenza.

## Variabili d'ambiente

| Variabile | Scopo | Sensibile |
|---|---|---|
| `SECRET_KEY` | Firma della sessione | Sì |
| `FLASK_ENV` | Configurazione applicativa | No |
| `APP_ENV` | Ambiente operativo: development, staging o production | No |
| `DATABASE_URL` | Connessione PostgreSQL di produzione | Sì |
| `MAIL_SERVER` | Server SMTP | No |
| `MAIL_PORT` | Porta SMTP | No |
| `MAIL_USE_TLS` | Abilitazione TLS SMTP | No |
| `MAIL_USE_SSL` | Abilitazione SSL SMTP alternativa a STARTTLS | No |
| `MAIL_SUPPRESS_SEND` | Sopprime fisicamente l'invio nello staging gratuito | No |
| `MAIL_USERNAME` | Account mittente | Sì |
| `MAIL_PASSWORD` | Password applicativa SMTP | Sì |
| `MAIL_DEFAULT_SENDER` | Nome/indirizzo mittente | Potenzialmente |
| `MAIL_ADMIN_RECIPIENT` | Destinatario interno degli avvisi | Potenzialmente |
| `CALENDARIO_CACHE_SECONDI` | Durata cache calendario, default 300 | No |
| `CALENDARIO_CACHE_STALE_SECONDI` | Età massima del fallback Calendar, default 900 | No |
| `CALENDARIO_CACHE_ERRORE_SECONDI` | Pausa del circuito dopo un errore Calendar, default 30 | No |
| `GOOGLE_CALENDAR_TIMEOUT_SECONDI` | Timeout HTTP Calendar per operazione, default 5 | No |
| `CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI` | Freschezza del controllo rapido all’ingresso admin, default 180 | No |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Percorso della credenziale API per lettura e scrittura | Sì |
| `GOOGLE_CALENDAR_ID` | Calendario operativo sincronizzato con Arzamed | Sì |
| `GOOGLE_ANALYTICS_ID` | ID GA4 | No |
| `PUBLIC_BASE_URL` | Origine HTTPS canonica del sito pubblico | No |
| `SONNO_CALL_URL` | Link opzionale della videochiamata inserito nelle conferme | Potenzialmente |
| `ADMIN_BOOTSTRAP_USERNAME` | Nome del primo amministratore, solo per il bootstrap | Sì |
| `ADMIN_BOOTSTRAP_PASSWORD` | Password del primo amministratore, solo per il bootstrap | Sì |
| `STAGING_AUTH_USERNAME` | Utente della protezione HTTP dello staging | Sì |
| `STAGING_AUTH_PASSWORD` | Password della protezione HTTP dello staging | Sì |
| `STAGING_LIVE_INTEGRATIONS` | Opt-in per email e Calendar reali nella preproduzione privata pagata | No |

Le credenziali restano in `.env` o nel secret manager dell'hosting. Il JSON dell'account di servizio non va committato.

### Matrice di configurazione Render

L'applicazione esegue una validazione fail-fast a ogni avvio. Per staging e
produzione sono obbligatori `FLASK_ENV=production`, una `SECRET_KEY` stabile di
almeno 32 caratteri e una `DATABASE_URL` PostgreSQL esplicita. Session cookie e
schema URL sono HTTPS; `ProxyFix` accetta un solo livello del proxy Render.

Lo staging gratuito usa:

| Chiave | Configurazione |
|---|---|
| `FLASK_ENV` | `production` |
| `APP_ENV` | `staging` |
| `SECRET_KEY` | generata da Render |
| `DATABASE_URL` | collegamento interno al PostgreSQL dello stesso Blueprint |
| `MAIL_SUPPRESS_SEND` | `true`, perché il piano gratuito blocca le porte SMTP |
| `ADMIN_BOOTSTRAP_USERNAME` | valore segreto scelto dall'attività |
| `ADMIN_BOOTSTRAP_PASSWORD` | valore segreto distinto, almeno 16 caratteri |
| `STAGING_AUTH_USERNAME` | valore segreto per i tester |
| `STAGING_AUTH_PASSWORD` | valore segreto distinto, almeno 16 caratteri |

Nello staging iniziale non inserire credenziali SMTP, Calendar reale o
Analytics. I dati sono esclusivamente fittizi. Dopo il primo login riuscito,
rimuovere `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD`, salvare e
ridistribuire; `bootstrap-admin` verificherà l'account già presente.

### Preproduzione privata con integrazioni reali

Stato verificato il 23 agosto 2026, prima dell'attivazione:

| Chiave o controllo | Stato |
|---|---|
| `FLASK_ENV` | `production` |
| `APP_ENV` | `staging` |
| `MAIL_SUPPRESS_SEND` | `true` |
| `STAGING_LIVE_INTEGRATIONS` | `false` |
| `STAGING_AUTH_*` | presenti |
| `ADMIN_BOOTSTRAP_*` | rimossi dopo il primo accesso |
| configurazione Zimbra e `GOOGLE_CALENDAR_ID` | presente, valori non documentati |
| `google-calendar-service-account.json` | assente |
| dominio personalizzato | assente |

Il collaudo di SMTP e Calendar avviene su un Web Service a pagamento ancora
configurato come `APP_ENV=staging`: Basic Auth, `robots.txt` bloccante e
`X-Robots-Tag` restano obbligatori. Sono ammessi esclusivamente dati sintetici,
destinatari email controllati ed eventi Calendar chiaramente riconoscibili,
rimossi al termine della prova.

Per abilitare questa fase impostare insieme:

- `STAGING_LIVE_INTEGRATIONS=true`;
- `MAIL_SUPPRESS_SEND=false`;
- la configurazione Zimbra e Calendar completa indicata nella matrice di
  produzione.

Senza l'opt-in esplicito la preproduzione continua a richiedere
`MAIL_SUPPRESS_SEND=true` e resta quindi incapace di inviare email per errore.
`flask --app app validate-config` verifica anche
server `smtp.mail.ovh.net`, porta 587, TLS attivo, SSL disattivo, casella
mittente approvata e presenza del secret file Google, senza mostrare valori
sensibili.

#### Esito del collaudo P0 del 24–26 agosto 2026

La preproduzione privata è stata attivata intenzionalmente con dati e
destinatari sintetici. Il collaudo reale ha verificato:

- ricezione su Zimbra della notifica amministrativa e della conferma al
  paziente, con mittente, destinatario, oggetto, servizio, data, ora, durata,
  testo e tracciamento nell'admin corretti;
- salvataggio e conferma della pratica anche con password SMTP temporaneamente
  invalida, registrazione separata dei due errori email e nessun rollback del
  dato principale;
- creazione, modifica e cancellazione dello stesso evento Calendar, inclusa
  una data invernale a `Europe/Rome`, senza slittamenti o duplicati;
- rilevazione di una modifica esterna, confronto sito/Calendar e ripristino dei
  dati locali tramite decisione amministrativa;
- degradazione dopo indisponibilità Calendar, persistenza locale e retry
  automatico reale del 25 agosto alle 19:19 con esito `1/1` riuscito, senza
  duplicati;
- riconoscimento di `status="cancelled"` come eliminazione esterna, avviso
  prioritario, ripristino con nuovo evento oppure annullamento ordinario con
  email al paziente.

Il primo test Calendar della build precedente resta registrato come fallimento:
un ID errato con accessi ripetuti aveva prodotto errori TLS, `502`, code 139 e
riavvio del worker. Le prove successive a D-080, D-081 e D-082 hanno superato il
perimetro corretto. Al termine tutti gli appuntamenti sintetici sono stati
eliminati; log tecnici e audit restano conservabili come evidenza. D-084 chiude
gli step 8, 9 e 13 della roadmap, ma non autorizza l'apertura pubblica e non
sostituisce i collaudi specifici dei flussi corsi e consulenza sonno. Lo stato
corrente del pannello dopo la prova va riconciliato prima del prossimo deploy.

Prima dell'apertura pubblica la produzione richiede inoltre:

| Chiave/file | Configurazione prevista |
|---|---|
| `APP_ENV` | `production` |
| `MAIL_SERVER` | `smtp.mail.ovh.net` per Zimbra Starter Europa |
| `MAIL_PORT` | `587` |
| `MAIL_USE_TLS` / `MAIL_USE_SSL` | `true` / `false` |
| `MAIL_SUPPRESS_SEND` | `false` |
| `MAIL_USERNAME` | casella completa `info@scstudioinfermieristico.it` |
| `MAIL_PASSWORD` | segreto SMTP inserito nel pannello |
| `MAIL_DEFAULT_SENDER` | `S.C. Studio Infermieristico <info@scstudioinfermieristico.it>` |
| `MAIL_ADMIN_RECIPIENT` | `info@scstudioinfermieristico.it`, definito in D-068 |
| `GOOGLE_CALENDAR_ID` | identificativo del calendario operativo |
| secret file `google-calendar-service-account.json` | JSON caricato dal pannello, disponibile in `/etc/secrets/` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `/etc/secrets/google-calendar-service-account.json` |
| `PUBLIC_BASE_URL` | origine HTTPS definitiva, senza percorso, per esempio `https://scstudioinfermieristico.it` |
| `GOOGLE_ANALYTICS_ID` | facoltativo finché informativa, consenso e GA4 non sono validati |
| `SONNO_CALL_URL` | facoltativo finché il collegamento non è definitivo |

`MAIL_USE_TLS` e `MAIL_USE_SSL` non possono essere entrambe attive. Sessione,
admin e Basic Auth devono usare segreti diversi. Il comando
`flask --app app validate-config` verifica la presenza e la coerenza senza
mostrare i valori.

### Consenso Analytics

Lasciare `GOOGLE_ANALYTICS_ID` non configurato finché l'informativa e la
configurazione GA4 non sono state validate. Quando l'ID è presente, lo script
esterno di Google non viene richiesto prima dell'accettazione. L'accettazione
parte da Consent Mode negato e concede soltanto `analytics_storage`; il rifiuto
o la revoca ripristinano tutte le categorie Analytics/Ads a `denied`, bloccano
gli eventi di conversione e fanno scadere i cookie `_ga*`, `_gid` e `_gat*`
del dominio. Gli altri cookie applicativi non vengono rimossi.

GA4 e Meta restano disattivati negli ambienti operativi fino alla validazione
professionale e al collaudo esplicito del comportamento sul dominio definitivo.

In produzione non esistono fallback Gmail per server SMTP o destinatario
amministrativo: ogni valore deve essere configurato esplicitamente. Canonical,
Open Graph, dati strutturati e link assoluti nelle email usano
`PUBLIC_BASE_URL`, così una richiesta arrivata dal sottodominio Render non lo
trasforma nell'origine pubblica del sito.

In produzione i log vengono inviati soltanto a stdout/stderr per Render. Non
viene creato `app.log`; le operazioni email registrano ID interni e tipo di
errore, non indirizzi dei destinatari. Non inserire mai token, password,
contenuto dei questionari o dati identificativi nei log.

### Timestamp e fuso orario

Gli istanti tecnici e di audit (`creato_il`, `aggiornato_il`, invii, risoluzioni,
archiviazioni e scadenze relative) sono salvati nelle colonne `DateTime` come
UTC senza offset, secondo una convenzione applicativa unica compatibile con
SQLite e PostgreSQL. L'area admin li interpreta come UTC e li converte con
`ZoneInfo('Europe/Rome')`; l'etichetta visibile `CET` o `CEST` mantiene
distinguibili anche le due occorrenze della stessa ora durante il ritorno
all'ora solare. Le date e gli orari civili scelti per appuntamenti, corsi e
attività restano invece valori locali italiani. Non impostare `TZ` sul server
come sostituto di questa conversione.

I timestamp storici creati sul servizio Render vengono interpretati come UTC:
non serve riscrivere le righe né modificare lo schema. Dopo ogni deploy
verificare nell'admin almeno un istante noto e, nei test automatici, entrambi i
passaggi CET/CEST.

## Modelli principali

- `Admin`: utente dell'area riservata.
- `Appuntamento`: prenotazione sanitaria e relativo stato.
- `CallSonno`: richiesta breve, stato, slot Calendar e invito al questionario.
- `QuestionarioSonno`: risposte private raccolte soltanto dopo la call.
- `Corso`: singola data di corso/laboratorio.
- `PersonaCorso`: rubrica dei partecipanti e delle famiglie.
- `IscrizioneCorso`: richiesta collegata, quando possibile, a corso e persona.
- `PercorsoAccompagnamento`: edizione del corso nascita completo.
- `IncontroAccompagnamento`: incontro di una specifica edizione.
- `PresenzaAccompagnamento`: registro presenze.
- `RegistroEvento`: log di email, sincronizzazioni ed errori parziali.
- `AttivitaAdmin`, `NotaAdmin`: prossime azioni e note cronologiche.
- `EmailOperativa`: copia esatta di destinatario, oggetto, corpo ed esito per 24 mesi.
- `PropostaSlot`, `BloccoAgenda`: proposte accettabili e pause/chiusure sincronizzate.
- `RegistroModifica`, `CollegamentoPersona`: audit amministrativo e collegamenti manuali tra pratiche.

Le regole di prodotto e i conteggi posti sono descritti in `SITE_MAP_AND_FLOWS.md`.

## Stati

- Appuntamenti: `In attesa`, `Confermato`, `Concluso`, `Assente`, `Annullato`.
- Call sonno: `In attesa`, `Confermata`, `Annullata`, `Conclusa`.
- Iscrizioni corso: `Nuova`, `Contattato`, `Confermato`, `Lista attesa`, `Invitato`, `Annullato`.
- Corsi: `Aperto`, `Completo`, `Chiuso`, `Annullato`, `Concluso`.
- Percorsi nascita: `Bozza`, `Aperto`, `Chiuso`, `Concluso`.

Le richieste corso senza data usano `tipo_richiesta = ricontatto`, mostrato in admin come `Da ricontattare`; non è uno stato aggiuntivo. Conservano il normale stato iniziale `Nuova`, occupano zero posti e proseguono poi negli stati corso già elencati. Il modulo unico della homepage registra anche la tematica scelta senza richiedere i dati amministrativi di un'iscrizione.

### Mail operative delle iscrizioni corso

- L’invio di un modulo pubblico o privato salva la richiesta in stato `Nuova` e manda soltanto l’alert interno a `MAIL_ADMIN_RECIPIENT`; non invia una ricevuta al partecipante.
- Per una richiesta collegata a una data, l’email del partecipante è obbligatoria perché costituisce il canale della successiva conferma.
- Il passaggio admin a `Confermato` invia la mail con corso, edizione e tipo di partecipazione. Un secondo passaggio sullo stesso stato non reinvia nulla.
- Il passaggio ad `Annullato` e lo spostamento individuale verso un’altra edizione inviano le relative comunicazioni. Lo spostamento di una richiesta ancora `Nuova` chiarisce che il posto resta non confermato.
- Stato e nuova edizione vengono salvati prima dell’invio SMTP. Un errore email non annulla l’operazione: resta tracciato in `EmailOperativa` e `RegistroEvento` e viene mostrato nell’admin.

## Google Calendar e Arzamed

- Lettura e scrittura usano Google Calendar API con un unico account di
  servizio e lo scope limitato agli eventi. Non viene usato alcun URL iCal.
- La lettura chiede a Google le singole occorrenze degli eventi nell'intervallo
  giornaliero, comprese le ricorrenze espanse, e usa una cache controllata da
  `CALENDARIO_CACHE_SECONDI`.
- Ogni operazione costruisce un trasporto HTTP autenticato distinto: nessun
  client `httplib2` viene condiviso fra thread, richieste web e scheduler. Il
  timeout è limitato da `GOOGLE_CALENDAR_TIMEOUT_SECONDI` e le route web non
  eseguono retry sincroni prolungati.
- Le letture concorrenti della stessa giornata vengono accorpate. Dopo un
  errore, il circuito sospende temporaneamente nuovi tentativi e usa, quando
  disponibile, una copia non più vecchia di
  `CALENDARIO_CACHE_STALE_SECONDI`. Cache e circuito sono locali al processo;
  un futuro aumento dei worker richiederà un coordinamento condiviso oppure
  accetterà un tentativo per ciascun processo.
- Lo stesso account di servizio crea o aggiorna eventi quando appuntamenti o
  corsi vengono confermati; le call sonno vengono invece inserite subito come
  provvisorie per bloccare lo slot anche in Arzamed.
- Gli eventi creati in Arzamed espongono su Google Calendar inizio e fine
  effettivi, che il sito usa integralmente per rilevare i conflitti. Una
  richiesta sanitaria dal sito blocca inizialmente 30 minuti; prima di
  confermarla l'admin deve scegliere la durata effettiva, da 1 a 480 minuti. Il
  valore viene salvato in `Appuntamento.duration_minutes` e
  determina conflitti, disponibilità e fine dell'evento Calendar.
- L'account di servizio deve avere sul solo calendario operativo il permesso di
  modificare gli eventi, non quello di gestire la condivisione.
- Un conflitto con un evento Calendar impedisce la conferma di quell'intervallo,
  ma non elimina la richiesta: l'admin riceve un avviso e può modificarla. Un
  errore secondario durante la successiva scrittura Calendar non annulla invece
  la conferma già salvata.
- Ogni ora il job riprova prima le pratiche attive in stato `da_sincronizzare`, `errore` o `mancante` e invia all’amministratore un’unica email riepilogativa se ha effettuato almeno un tentativo. Se manca il `google_event_id`, cerca prima una corrispondenza tramite le proprietà private della pratica per non duplicare un evento creato prima di un timeout. Subito dopo, la riconciliazione confronta titolo, inizio e fine degli eventi collegati; `404/410` e una risposta con `status="cancelled"` indicano entrambi eliminazione esterna.
- L’ingresso in `/admin` esegue lo stesso confronto soltanto quando l’ultimo controllo del processo è più vecchio di `CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI`. Usa client isolato, timeout e circuito di D-080; un errore o una risposta non valida mostra un avviso ma non impedisce l’apertura dell’admin. Il deploy corrente usa un worker; con più worker la finestra resta locale al processo come la cache Calendar.
- Gli stati `difforme` ed `eliminato_esternamente` aprono un avviso prioritario, restano esclusi da autoretry, sincronizzazione in blocco e chiusura manuale generica. Una modifica temporale accettata da Calendar ricontrolla disponibilità, aggiorna il database, registra l’audit, riallinea il titolo canonico e invia l’email di spostamento. Un evento eliminato viene ricreato con nuovo ID senza email oppure porta al normale annullamento con email. `Decidi dopo` non modifica la pratica e non chiude l’anomalia.
- Gli eventi non creati dal sito vengono mostrati in agenda con titolo e orario, senza importarli né attribuirli automaticamente ad Arzamed. Non esiste un identificativo Arzamed nel database finché non sarà disponibile un’integrazione diretta stabile.

## Errori parziali

Il dato principale ha priorità:

- una prenotazione non deve andare persa se l'email fallisce;
- un'iscrizione non deve andare persa se Calendar fallisce;
- un corso non deve scomparire per un errore di sincronizzazione.

Dopo il salvataggio, gli errori secondari devono essere registrati in `RegistroEvento`. Quando l'errore riguarda un'azione admin, mostrare un avviso comprensibile senza fingere che l'intera operazione sia fallita.

Un errore Calendar non deve propagarsi come errore HTTP del sito: la pratica
locale resta salvata, la sincronizzazione passa in stato di errore e il primo
job orario utile ritenta automaticamente la scrittura. Il ciclo invia una sola
email con esito riuscito, fallito o parziale; un fallimento viene riprovato nel
ciclo successivo. In assenza di una copia
Calendar ancora valida, la disponibilità continua a includere i dati locali ma
non deve essere considerata una prova che Arzamed sia libero.

## Sicurezza

- CSRF manuale tramite `_csrf_token` di sessione; verificare ogni nuovo form che modifica dati.
- Rate limiting almeno su prenotazione e login.
- Cookie sicuri in produzione.
- Nessun segreto hardcoded.
- Nessun dato personale nei log oltre ciò che è realmente necessario.
- Confermare che la CSP autorizzi soltanto origini indispensabili.
- Proteggere route private e admin con autenticazione e controllo degli identificativi.
- Il lancio usa un solo account, senza ruoli o assegnazioni. La sessione permanente scade dopo 60 minuti di inattività e il login conserva il limite di cinque tentativi al minuto.

### Credenziale admin iniziale

Non esistono credenziali predefinite. In locale il primo amministratore si crea
con `flask --app app create-admin`, che richiede una password di almeno 16
caratteri. Su un database di produzione vuoto l'avvio richiede entrambe le
variabili `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD`; se una manca,
l'applicazione si arresta. Dopo il primo accesso riuscito, rimuovere entrambe le
variabili dal gestore dei segreti: l'account resta nel database e gli avvii
successivi non ne dipendono.

## Database e migrazioni

La baseline Alembic `56dda7f5137f` crea lo schema iniziale; la revisione corrente del repository è
`e2f4a6b8c901`, mentre l’ultima revisione verificata nella preproduzione privata resta `d91e6b4f2a30` finché non viene eseguito un nuovo deploy. Le revisioni aggiungono qualificazione, UTM e stato dei
promemoria email alla call sonno, rimuovono i campi del precedente promemoria
WhatsApp, aggiungono la durata effettiva, introducono la regia operativa admin, normalizzano le difformità dei database SQLite legacy e portano `iscrizione_corso.data_corso` da 20 a 255 caratteri per contenere data, ora e luogo dell’edizione. Un nuovo
database, SQLite o PostgreSQL, si prepara esclusivamente con:

```bash
flask --app app db upgrade
flask --app app db check
```

L'importazione di `app.py` non crea tabelle. `db.create_all()` resta confinato
agli helper di test e non viene usato per avviare o far evolvere staging e
produzione.

Per ogni modifica futura ai modelli:

1. generare `flask --app app db migrate -m "descrizione"` su un database di sviluppo aggiornato;
2. revisionare manualmente upgrade, downgrade, vincoli, nullability e valori esistenti;
3. provare upgrade su database vuoto e su una copia sintetica o anonimizzata rappresentativa;
4. eseguire `flask --app app db check` e la suite completa;
5. applicare la migrazione in staging prima della produzione.

Per adottare un database SQLite legacy già identico allo schema della baseline,
fare prima un backup e confrontare lo schema, quindi usare `flask --app app db
stamp head`. Il comando registra soltanto la revisione e non modifica le
tabelle. Se lo schema non è già allineato, eseguire prima le migrazioni una
tantum pertinenti su una copia e verificarne i dati. Non applicare direttamente
la baseline con `upgrade` a tabelle preesistenti.

Per database SQLite legacy, eseguire una sola volta e nell'ordine:

```bash
python3 migrazione_google_event_id.py
python3 migrazione_corsi_google_event_id.py
python3 migrazione_gestione_iscritti_corsi.py
python3 migrazione_registro_eventi.py
python3 migrazione_call_sonno.py
```

Non eseguire migrazioni una tantum alla cieca su dati reali. Fare prima un backup e verificare lo schema.

`migrazione_call_sonno.py` è idempotente anche quando `call_sonno` o
`questionario_sonno` esistono già: aggiunge soltanto le colonne additive
mancanti, conserva le righe presenti e non attribuisce retroattivamente il
consenso privacy, che resta falso se non era stato registrato.


Se un database legacy possiede già le tabelle ma `alembic_version` è vuota,
identificare prima la revisione realmente rappresentata dallo schema, crearne
una copia e usare `stamp <revisione>` prima di `upgrade`. Non usare `stamp
head` per aggirare colonne mancanti: registra uno stato falso e non le crea.

La baseline è stata verificata generando anche SQL PostgreSQL e con prove
automatiche di upgrade ripetuto su database vuoto e adozione di uno schema
rappresentativo popolato. Non usare `db.create_all()` per database operativi.

## Backup e ripristino PostgreSQL

### Livelli di protezione

1. **Render PITR:** obbligatorio prima dei dati reali. Sul workspace Hobby il database PostgreSQL a pagamento conserva una finestra point-in-time di 3 giorni. Un ripristino genera un nuovo database da verificare prima di cambiare `DATABASE_URL`.
2. **Export logico locale:** `scripts/backup_postgres.sh` esegue ogni giorno `pg_dump` in formato custom, cifra il dump con AES-256 e PBKDF2, genera SHA-256 e conserva la copia sul PC dell'attività.
3. **Export Render manuale:** creare un export dalla sezione Recovery prima di migrazioni rischiose o interventi straordinari; Render conserva questi export per 7 giorni, quindi scaricarli se devono durare più a lungo.

Il database gratuito resta soltanto uno staging storico con dati fittizi e non
viene aggiornato né promosso. Il 23 agosto è stato creato il PostgreSQL pagato,
nuovo e senza dati commerciali o sanitari, previsto da D-061 e
`render.production.yaml`; il pannello Recovery ha confermato una finestra PITR
di tre giorni. Prima dei dati reali resta obbligatorio affiancargli l'export
logico cifrato esterno.

### Obiettivi e conservazione

- backup locale: ogni giorno alle 21:00, con controllo dell'esito il mattino successivo;
- giornalieri: 14 giorni;
- settimanali: 8 settimane, copia della domenica;
- mensili: 12 mesi, copia del primo giorno del mese;
- restore test: mensile e prima di migrazioni o modifiche distruttive;
- RPO esterno: massimo 24 ore; PITR copre perdite più recenti nella propria finestra;
- RTO obiettivo: ripristino del servizio entro 8 ore lavorative.

Il PC può svolgere il ruolo di destinazione esterna perché è controllato
dall'attività, ma non è l'unica protezione: deve affiancare il PITR Render. Sono
obbligatori FileVault, password dell'account, aggiornamenti, cartella non
condivisa pubblicamente, spazio libero monitorato e una copia offline della
password di cifratura. I backup contengono dati personali e potenzialmente
sanitari anche se cifrati; non vanno sincronizzati su servizi personali non
valutati.

### Preparazione del PC

Installare una versione di client PostgreSQL uguale o più recente del server.
Sul Mac di gestione sono stati installati PostgreSQL 18.4 e i relativi
`pg_dump`, `pg_restore` e `psql` tramite Homebrew. Scegliere una cartella
dedicata il cui percorso termini obbligatoriamente con `sc-studio-backups`.

Salvare l'URL esterno Render e una password di cifratura casuale di almeno 20
caratteri nel Portachiavi macOS, senza inserirli nella cronologia della shell:

```bash
security add-generic-password -U -s sc-studio-render-database-url -w
security add-generic-password -U -s sc-studio-backup-password -w
```

I comandi chiedono il valore in modo interattivo. Conservare la password di
cifratura anche offline, separata dal PC: senza di essa i backup sono
irrecuperabili.

Esecuzione manuale, usando un percorso di esempio da sostituire:

```bash
BACKUP_ROOT=/percorso/sc-studio-backups scripts/backup_postgres.sh
```

Programmare lo stesso comando ogni giorno alle 21:00 con `launchd` dopo la
creazione del database Render. Il job non deve contenere segreti: gli script li
leggono dal Portachiavi. Se il PC è spento o offline, l'esecuzione manca e va
recuperata manualmente; controllare data e checksum dell'ultimo file ogni
mattina. Log e notifiche automatiche vengono configurati insieme al database
reale, senza registrare l'URL di connessione.

### Ripristino

Creare sempre un database PostgreSQL vuoto e distinto. Non ripristinare sopra il
database operativo. Salvare temporaneamente il relativo URL nel Portachiavi:

```bash
security add-generic-password -U -s sc-studio-restore-database-url -w
scripts/restore_postgres.sh /percorso/sc-studio-backups/daily/NOME.dump.enc
```

Lo script verifica SHA-256, rifiuta destinazioni con tabelle, decifra in una
cartella temporanea con permessi restrittivi, usa `pg_restore` in una transazione
e conta le tabelle ripristinate. Dopo il restore verificare almeno revisione
Alembic, conteggi per tabella, login amministrativo e un flusso fittizio; solo
allora cambiare `DATABASE_URL`. Rimuovere dal Portachiavi l'URL temporaneo quando
non serve più.

### Evidenza del restore test iniziale

Il 20 luglio 2026 è stato eseguito un test completo su PostgreSQL 18.4 locale
temporaneo con soli dati sintetici: migrazione Alembic, dump custom, cifratura,
checksum, ripristino in database vuoto e verifica finale. Risultato: 12 tabelle
pubbliche, una riga admin sintetica, una prenotazione sintetica e revisione
`56dda7f5137f` correttamente recuperate. Server, database e backup temporanei
sono stati eliminati dopo il test.

## Comandi locali

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 -m flask --app app db upgrade
python3 -m flask --app app run
pytest
git diff --check
```

Aggiornare `requirements.txt` solo quando cambia realmente una dipendenza e controllare le differenze prodotte.

## Checklist di deploy

- Stato Git pulito e commit identificabile.
- Tutti i test superati.
- Migrazioni provate su una copia dei dati.
- Backup e procedura di ripristino verificati.
- `FLASK_ENV=production`, `SECRET_KEY` stabile e segreti configurati.
- `PUBLIC_BASE_URL` coincide con il dominio definitivo ed è indipendente
  dall'host `onrender.com`.
- Credenziale admin predefinita rimossa o sostituita.
- HTTPS e cookie sicuri verificati.
- Email reali testate con mittente corretto.
- Promemoria email delle call collaudati a 24h e 2h, inclusa la prevenzione dei duplicati.
- Lettura e scrittura Calendar testate con permessi minimi.
- Riconciliazione Calendar testata su modifica e cancellazione originate da Arzamed, più scrittura forzata dopo confronto.
- Giornata amministrativa simulata completata su desktop e mobile: richieste, urgenze, appuntamenti, corsi, lista d’attesa, attività ed errori.
- GA4 caricato solo dopo consenso.
- Privacy, cookie e policy operative validate.
- Log controllati e privi di dati personali superflui.
- Nome del logo normalizzato in `static/img/logo.png` e coerente con i riferimenti applicativi sui filesystem Linux case-sensitive.
- Controllo visivo desktop/mobile completato.

## Vista mensile e richieste organizzative

Dal 13 agosto 2026 il codice locale include:

- vista mensile dell’agenda, con massimo tre impegni sintetici per giorno, anteprima operativa dopo un secondo di hover e accesso alla vista giornaliera per il dettaglio;
- creazione manuale di appuntamenti anche senza telefono o email, subordinata a conferma esplicita e registrazione dei contatti mancanti nell’audit; gli errori restano nello stesso modulo senza cancellare i valori;
- selezione della data tramite calendario nativo e dell’orario tramite menu separati per ore e minuti, con granularità di cinque minuti;
- modulo pubblico `/aziende-e-gruppi`, limitato a cinque invii al minuto e protetto da CSRF;
- conferma al referente e avviso allo studio tramite la stessa infrastruttura SMTP tracciata;
- attività automatica alla ricezione e sostituzione della prossima attività quando cambia lo stato;
- proposta manuale inviata soltanto dopo conferma esplicita dell’operatore, con copia conservata nel registro email;
- conversione in corso privato con stato `Chiuso`, visibile in agenda e sincronizzato su Calendar ma escluso dalle date pubbliche;
- quiz `/da-dove-parto` eseguito solo nel browser, senza richieste di rete o persistenza delle risposte, con passaggi avanti e indietro che riusano direzione, durata e giunzione visiva delle transizioni laterali del sito.

La tabella è introdotta dalla revisione Alembic `c84f2d1a9e70`, successiva a `a13d8f7c2b40`. Prima di distribuire il codice eseguire `flask db upgrade` su una copia o su un database vuoto, quindi `flask db check`. D-084 prova l'infrastruttura SMTP/Calendar condivisa nella preproduzione privata, ma non il flusso organizzativo qui descritto: conversione, capienza, comunicazioni e Calendar del corso riservato conservano un collaudo specifico.

## Dati esclusi dalla documentazione

Non aggiungere a `docs/`:

- contenuto di `.env`;
- database o backup reali;
- JSON degli account di servizio;
- elenchi iscritti, pazienti o partecipanti;
- feedback non anonimizzati o prove di consenso.
