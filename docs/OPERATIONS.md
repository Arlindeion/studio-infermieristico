# Operatività tecnica

Revisione documentale: 22 ottobre 2026. Le evidenze esterne mantengono la propria data e non dimostrano da sole lo stato corrente dei pannelli.

## Stato operativo corrente — dominio privato, D-131

Il committente conferma il manual deploy di `3fe6033` e il funzionamento di `https://scstudioinfermieristico.it` con password. Il servizio resta una preproduzione privata su risorse pagate: non è stato autorizzato il GO pubblico. [Evidenze e limiti](VERIFICHE_RILASCIO_2026-10-22.md).

| Impostazione | Stato concordato / confermato dal committente |
|---|---|
| `FLASK_ENV` | `production`, runtime sicuro; distinto da `APP_ENV` |
| `APP_ENV` | `staging`, non cambiarlo prima del GO |
| `PUBLIC_BASE_URL` | `https://scstudioinfermieristico.it`, senza percorso |
| `STAGING_AUTH_USERNAME` / `STAGING_AUTH_PASSWORD` | mantenute, valori segreti; la Basic Auth resta obbligatoria |
| Dominio apex | DNS verificato e certificato emesso; accesso con password confermato |
| `www` | DNS verificato; ultimo certificato esplicitamente riferito ancora pending, da ricontrollare |
| Indicizzazione | mantenere blocco staging, `Disallow: /` e noindex; verifica diretta sul dominio ancora da documentare |
| Email / Calendar | nessuna modifica alle integrazioni in questa fase; D-124 resta vincolante per gli agenti |
| PayPal / Analytics | PayPal sospeso; nessuna nuova attivazione di analytics o campagna |

DNS OVH: apex A `216.24.57.1`, `www` CNAME `sc-studio-infermieristico-production.onrender.com.`. Non cambiare i record della posta o ripristinare la zona. Collegamento del dominio e apertura anonima sono operazioni distinte: ora è autorizzato soltanto il primo. Non togliere `STAGING_AUTH_*` restando staging.

Nel giorno scelto dal committente: verifiche della [checklist](PRE_GO_LIVE_CHECKLIST.md), GO esplicito, `APP_ENV=production`, stessa origine canonica, rimozione delle sole credenziali staging e deploy controllato. Protezioni admin, CSRF, rate limiting e privacy restano. Verificare HTTPS, redirect, URL email, pagine pubbliche indicizzabili e route private escluse prima di disabilitare l'eventuale sottodominio Render. Il codice di `3fe6033` non richiede una nuova migrazione.

Il Blueprint preparatorio non rappresenta automaticamente il pannello: prima di qualunque Sync confrontare ambiente, dominio e regole IP backup. Non eseguire un Sync per allineare questi documenti. Le sezioni datate seguenti conservano la storia di attivazione; per stato attuale prevale questo riepilogo e la sezione backup.

## Priorità di pubblicazione

Seguire [ROADMAP.md](ROADMAP.md) e [PRE_GO_LIVE_CHECKLIST.md](PRE_GO_LIVE_CHECKLIST.md), secondo D-123. Pubblicare l'attuale sito dopo i controlli essenziali, senza attendere campagne o nuove funzioni. PayPal è sospeso fino a nuovo ordine: `SONNO_PAYPAL_ENABLED = False` è una configurazione applicativa fissa, non attivabile con una variabile d'ambiente. I link legacy sono ignorati per le nuove scelte; i pagamenti storici restano consultabili. Per il sonno verificare soltanto bonifico e conferma manuale. I riferimenti generici a PayPal nelle condizioni versionate descrivono modalità eventualmente rese disponibili e non ne dichiarano l'attivazione.

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

Il Blueprint è una base di preproduzione privata; non certifica da solo le successive modifiche del pannello. Per dominio e accessi backup correnti vedere il riepilogo iniziale. In particolare:

- usa `main`, da portare sempre esattamente al commit approvato e verificato;
- crea Web Service Starter e PostgreSQL Basic-256mb separati in Francoforte;
- fissa il disco iniziale a 1 GB e disabilita l'autoscaling per evitare aumenti
  automatici di costo;
- colloca le risorse in un ambiente Render protetto e con rete privata isolata;
- nel file `ipAllowList: []` è la base chiusa; nel pannello sono state autorizzate soltanto le sorgenti backup puntuali, da preservare e verificare prima di un Sync;
- mantiene `APP_ENV=staging`, Basic Auth e `noindex`; email e integrazioni reali hanno avuto un'attivazione separata documentata nello storico, non modificarle per collegare il dominio;
- mantiene auto-deploy e preview disattivati;
- non dichiara il dominio nel file; il collegamento privato è stato effettuato dal pannello il 22 ottobre. Il sottodominio Render non è ancora attestato come disattivato;
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
8. collaudare i flussi con dati sintetici secondo le autorizzazioni: dal 20 ottobre D-124 vieta agli agenti ogni modifica di Calendar reale, inclusa la creazione o rimozione di eventi di prova; usare simulazioni;
9. restringere l'accesso esterno al database alla sola sorgente necessaria per
   il backup cifrato, dopo aver scelto una provenienza IP stabile; non usare
   `0.0.0.0/0`;
10. il collegamento DNS/dominio con password è autorizzato e confermato in D-131. Chiudere i gate essenziali e ottenere un ordine distinto prima di impostare `APP_ENV=production` o rendere pubblico il servizio.

Il dominio può quindi essere usato in staging protetto prima del GO. L'attivazione delle integrazioni in preproduzione richiede una modifica
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
| `PAYPAL_LINK_SONNO_MIRATA` | Legacy inattivo: non configurare per il lancio, D-123 | Potenzialmente |
| `PAYPAL_LINK_SONNO_PERCORSO` | Legacy inattivo: non configurare per il lancio, D-123 | Potenzialmente |
| `PAYPAL_LINK_SONNO_AFFIANCAMENTO` | Legacy inattivo: non configurare per il lancio, D-123 | Potenzialmente |
| `BONIFICO_INTESTATARIO` | Intestatario mostrato nella proposta privata | Potenzialmente |
| `BONIFICO_IBAN` | IBAN mostrato nella proposta privata | Sì |
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
| `PAYPAL_LINK_SONNO_MIRATA` / `PAYPAL_LINK_SONNO_PERCORSO` / `PAYPAL_LINK_SONNO_AFFIANCAMENTO` | legacy inattivi; PayPal sospeso fino a nuovo ordine, non configurare per il lancio (D-123) |
| `BONIFICO_INTESTATARIO` / `BONIFICO_IBAN` | facoltativi; configurarli nel secret manager per rendere disponibile il bonifico nella proposta privata |

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
- `Appuntamento`: prenotazione sanitaria, relativo stato e presa visione dell’informativa raccolta dal modulo.
- `CallSonno`: richiesta breve, stato, slot Calendar e invito al questionario.
- `QuestionarioSonno`: risposte private raccolte soltanto dopo la call.
- `Corso`: singola data di corso/laboratorio.
- `Persona`, `RecapitoPersona`: anagrafica Pazienti 2.0 attiva e relativi recapiti normalizzati; dal cutover sono l'unica destinazione delle nuove scritture amministrative.
- `CalendarPatientDecision`: riferimento tecnico e decisione amministrativa che collega o esclude un evento Calendar per una persona, senza copiarne titolo, orario, descrizione o note. Il vincolo parziale consente un solo collegamento `linked` per evento; le esclusioni `rejected` restano specifiche per persona.

- `PersonaCorso`: anagrafica legacy mantenuta temporaneamente in sola lettura per i record precedenti; non riceve nuove righe dopo il cutover D-117.
- `ConsensoPrivacyPaziente`: tabella storica che conserva stato e data della presa visione associata alla specifica pratica; ogni riga punta a una sola anagrafica, legacy oppure v2.
- `AutorizzazioneImmagini`: consenso facoltativo per una singola persona, con finalità, canali, responsabilità genitoriale, versione dell’informativa e revoca.
- `IscrizioneCorso`: richiesta collegata, quando possibile, a corso e persona.
- `PercorsoAccompagnamento`: edizione del corso nascita completo.
- `IncontroAccompagnamento`: incontro di una specifica edizione.
- `PresenzaAccompagnamento`: registro presenze.
- `RegistroEvento`: log di email, sincronizzazioni ed errori parziali.
- `AttivitaAdmin`, `NotaAdmin`: prossime azioni e note cronologiche.
- `EmailOperativa`: copia esatta di destinatario, oggetto, corpo ed esito fino al termine applicabile alla pratica collegata.
- `PropostaSlot`, `BloccoAgenda`: proposte accettabili e pause/chiusure sincronizzate.
- `RegistroModifica`: audit amministrativo minimizzato.
- `CollegamentoPersona`: collegamento legacy mantenuto in sola compatibilità di lettura; le nuove associazioni usano le FK Pazienti 2.0 sulle pratiche.

La revisione `e8b1c4d7a902` può essere annullata soltanto prima della prima
decisione Calendar-paziente. Se la tabella contiene anche una sola riga, il
downgrade si interrompe per non eliminare collegamenti, esclusioni e audit.

Le regole di prodotto e i conteggi posti sono descritti in `SITE_MAP_AND_FLOWS.md`.

## Conservazione privacy

La revisione Alembic `b7d2e4f6a810` introduce la tracciabilità delle autorizzazioni immagini, del consenso specifico ai dati della gravidanza, della consegna in presenza dell’informativa ai terzi e dell’anonimizzazione. Il job giornaliero applica termini distinti senza cancellare i riepiloghi operativi:

- 6 mesi dalla chiusura per ricontatti senza prenotazione e richieste aziendali;
- 12 mesi dalla conclusione per iscrizioni a corsi, percorsi nascita e consulenze educative sul sonno;
- 24 mesi dalla conclusione per i dati organizzativi degli appuntamenti sanitari.

Alla scadenza vengono rimossi recapiti, codici fiscali, note, questionari, token e dati extra identificativi; corso, data, stato, posti e conteggi restano disponibili in forma anonima. Note amministrative e dettagli tecnici collegati vengono rimossi o minimizzati. Le copie email seguono lo stesso termine della pratica, salvo il termine di 24 mesi per le tipologie senza un termine più breve. Le autorizzazioni immagini restano separate perché devono documentare il consenso finché l’immagine è utilizzabile e la revoca interrompe ogni nuovo utilizzo.

La procedura tratta soltanto pratiche concluse, annullate, archiviate o attività terminate da almeno il relativo periodo. Documentazione sanitaria e fiscale soggetta a obblighi autonomi non viene rappresentata dalle tabelle organizzative anonimizzate e deve restare nei sistemi professionali competenti. Ogni esecuzione che modifica dati crea un evento aggregato `privacy`, privo di dati personali.

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
- Il passaggio dell’intera edizione a `Annullato`, anche dal modulo di modifica, registra il timestamp di archiviazione, elimina l’evento Calendar e invia automaticamente l’avviso ai soli partecipanti `Confermato`; ripetere lo stesso stato non reinvia la mail. Il comando `Archivia` applica lo stesso flusso. Se manca il `google_event_id` locale, il sistema cerca prima l’evento tramite le proprietà private `studioEntity` e `studioEntityId`, evitando di dichiarare conclusa la cancellazione mentre l’evento remoto esiste ancora.
- Gli stati `Lista attesa` e `Invitato` non ricevono email: quando si libera un posto viene creata un’attività admin per il contatto telefonico. Il passaggio successivo a `Confermato` invia la normale conferma del posto.
- La modifica organizzativa di un’edizione viene salvata anche senza selezionare l’invio ai destinatari; la checkbox controlla soltanto gli aggiornamenti ordinari e non la persistenza o la sincronizzazione Calendar. L’avviso dovuto all’annullamento dell’intera edizione è automatico e indipendente dalla checkbox.
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

La baseline Alembic `56dda7f5137f` crea lo schema iniziale; la revisione corrente
del repository è `d4a7c2e9f610`, mentre l'ultima revisione verificata nella
preproduzione privata resta `d91e6b4f2a30` finché non viene eseguito un nuovo
deploy. Le revisioni aggiungono qualificazione, UTM e stato dei promemoria email
alla call sonno, rimuovono i campi del precedente promemoria WhatsApp, aggiungono
la durata effettiva, introducono la regia operativa admin, normalizzano le
difformità dei database SQLite legacy, portano `iscrizione_corso.data_corso` da
20 a 255 caratteri, rendono facoltativo `persona_corso.telefono` e introducono
schema, backfill e cutover di Pazienti 2.0. Un nuovo database, SQLite o
PostgreSQL, si prepara esclusivamente con:

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
mancanti, conserva le righe presenti e non attribuisce retroattivamente la
presa visione dell’informativa, che resta falsa se non era stata registrata.


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
2. **Export logico locale:** due job indipendenti Mac/Windows, dump custom cifrato age e SHA-256 (D-126–D-128). Stato corrente e procedure sono nella sezione seguente; il precedente script OpenSSL resta solo per compatibilità storica.
3. **Export Render manuale:** creare un export dalla sezione Recovery prima di migrazioni rischiose o interventi straordinari; Render conserva questi export per 7 giorni, quindi scaricarli se devono durare più a lungo.

Il database gratuito resta soltanto uno staging storico con dati fittizi e non
viene aggiornato né promosso. Il 23 agosto è stato creato il PostgreSQL pagato,
nuovo e senza dati commerciali o sanitari, previsto da D-061 e
`render.production.yaml`; il pannello Recovery ha confermato una finestra PITR
di tre giorni. Prima dei dati reali resta obbligatorio affiancargli l'export
logico cifrato esterno.

### Obiettivi e conservazione

- backup locale: Windows alle 21:00, Mac alle 22:00, con controllo dell'esito il mattino successivo;
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

### Stato corrente Mac e Windows — 22 ottobre 2026

Le due macchine eseguono export indipendenti: non si replicano a specchio e non
richiedono porte aperte tra le reti. Il PC Windows normalmente acceso sostiene
l'obiettivo della copia entro 24 ore; il Mac può essere spento o in stop.
Le due reti non attestano due sedi fisiche distinte. Le copie online non sono
immutabili né sostituiscono PITR e chiave di recupero separata.

- **Windows:** il committente ha riportato BitLocker attivo, backup cifrato e
  controllo integri, decifratura riuscita e restore locale isolato con 28
  tabelle; database di collaudo eliminato. L'attività `SCStudioBackup`, account
  Windows corrispondente al profilo che ha configurato DPAPI, è pianificata alle
  21:00. Avvio da Task Scheduler del 21 ottobre 23:43:19: risultato 0 e stato
  `success`. Restano da provare esecuzione dopo disconnessione/riavvio; avviso
  remoto a 72 ore attivo come descritto sotto. Procedura:
  [pacchetto Windows](../scripts/windows-backup/README.md).
- **Mac:** FileVault confermato attivo; client PostgreSQL 18.4 e age 1.3.2
  disponibili. Pacchetto [macOS](../scripts/macos-backup/README.md) installato
  nella cartella privata `~/Library/Application Support/SCStudioBackup`.
  Collaudo sintetico completo dump/cifratura/decifratura/restore riuscito su
  PostgreSQL temporaneo, senza dati reali o chiave privata esistente. Primo
  backup reale cifrato riuscito il 22 ottobre, controllo locale di integrità
  superato e password dedicata salvata nel Portachiavi con inserimento locale
  del committente. LaunchAgent attivato alle 22:00: primo controllo automatico
  concluso con codice 0, export saltato perché già coperto dal backup manuale.
  Collaudo aggiuntivo del 22 ottobre: nuovo export reale eseguito da un job
  `launchd` temporaneo in background, accesso al Portachiavi senza inserimento
  interattivo, archivio integro, una sola esecuzione e codice 0; job temporaneo
  rimosso, pianificazione notturna invariata. Un primo job di collaudo con
  `launchctl submit` era stato rilanciato da macOS e ha creato copie aggiuntive
  valide: rimosso e sostituito per la verifica da un plist con `KeepAlive=false`.
  Nessuna copia reale cancellata. La prima esportazione alla scadenza delle
  22:00, il recupero fisico dopo stop/riavvio e il restore del nuovo archivio
  reale Mac non sono ancora collaudati.
- **Rete Render:** aggiunta con autorizzazione la sola regola `/32` dell'IP
  pubblico corrente del Mac, conservando invariata la regola Windows. Nessuna
  apertura indiscriminata. Con IP dinamici aggiornare solo la regola puntuale
  dopo verifica. Usare `studio_backup`, TLS `verify-full` e credenziali protette
  da DPAPI/Portachiavi, mai nei job o nella documentazione.

Il nuovo Mac usa la stessa chiave **pubblica** age del Windows. La chiave
privata di recupero, già copiata separatamente secondo conferma del committente,
non viene letta dalla procedura di backup. Pianificazione Mac prevista con
LaunchAgent: 22:00 locali, verifica all'accesso e tentativi orari solo se dovuti.
In stop recupera al risveglio; da spento non esegue e riparte solo dopo login.
Nessuna modifica alle impostazioni energetiche globali. Per gli avvisi remoti
vedere la sezione seguente; verificare comunque `logs/status.json` e `--check`.

Entrambe le destinazioni hanno ora una copia reale riuscita; non è ancora
attestata la continuità delle esecuzioni dopo stop/riavvio. Nessuna operazione su Calendar; nessun
avvio dell'applicazione durante dump e restore isolati. A5 (ex R5) resta aperta per i
collaudi mancanti e il controllo operativo degli errori.

Il collaudo autonomo Mac comprende 18 prove dedicate, incluso il ciclo reale
di strumenti PostgreSQL/age con dati sintetici e confronto dopo restore su
database isolato. Guasti simulati di Portachiavi, dump, verifica e cifratura
preservano la copia precedente, puliscono i temporanei e consentono un nuovo
tentativo riuscito; spazio insufficiente blocca prima di leggere credenziali.
Verificate anche corruzione, conservazione protetta, mutua esclusione,
scadenze/ora legale e permessi. Queste prove non attestano la consegna di un
avviso remoto. Non è stata interrotta la rete reale,
né messo il Mac in stop o riavviato. Il PostgreSQL temporaneo è stato arrestato
al termine; applicazione e Calendar non sono stati avviati.

### Monitor remoto dei backup — D-129

Su richiesta del committente sono stati creati nell'account Healthchecks dello
studio due controlli indipendenti, `Backup Mac` e `Backup Windows`, con periodo
71 ore e tolleranza 1 ora: avviso dopo 72 ore senza segnale di un nuovo backup
riuscito anche su una sola macchina. Integrazione email alla casella Gmail
dello studio già verificata, **solo down**; report mensili/settimanali/giornalieri
e reminder ripetuti disattivati, nessuna email di ripristino. Non è un reminder
di calendario e non interviene su Calendar.

Stato: servizio esterno configurato; Mac collegato e attivo dopo nuovo backup
reale riuscito, segnale confermato dal client e visibile in Healthchecks.
Email tecnica di prova inviata: Healthchecks riporta `Delivered`; ricezione
effettiva nella casella confermata dal committente. Windows aggiornato con i tre
file aggiuntivi verificati tramite SHA-256, URL protetto con DPAPI e prova
manuale riuscita. Il committente ha poi aggiornato l'azione dell'attività
esistente, riconfermando localmente la password dello stesso account Microsoft.
La modifica senza credenziale era stata rifiutata e verificata come non
applicata; nessuna attività è stata cancellata o ricreata. Definizione precedente
conservata in `config/SCStudioBackup-before-monitor.xml` sul PC, non nel repository.

Collaudo Windows tramite avvio dell'attività del 22 ottobre alle 00:49:34 locali:
stato finale `Ready`, `LastTaskResult=0`, nuovo backup `success/completato` alle
00:49:35 locali e monitor `success` alle 00:49:41; prossima esecuzione alle
21:00 del 22 ottobre. Esiti locali riportati dal committente tramite AnyDesk;
nessun accesso diretto dell'agente al PC. Verifica diretta della dashboard
Healthchecks: entrambi i controlli verdi, segnale Windows recente e distinto
da quello Mac. Entrambi i monitor sono quindi armati e attivi. Non è stato
simulato un guasto reale di tre giorni o un riavvio fisico delle macchine.
Un eventuale nuovo controllo `Never` non è armato: non inviare segnali fittizi.

Per preservare le correzioni già applicate sul PC, l'aggiornamento Windows è
un'aggiunta separata: `Backup-Monitored.ps1`, `StudioMonitor.psm1`,
`Enable-Monitor.ps1`. Non sovrascrive il backup o il modulo originali. Dopo
configurazione DPAPI e nuovo backup/segnale verificati, sostituire nell'unica
azione del task esistente il file `Backup.ps1` con `Backup-Monitored.ps1`,
conservando account, opzioni, eseguibile, orario e cartella di lavoro.
Collaudo sintetico del wrapper su PowerShell 7: nuovo successo invia il
segnale; errore e successo senza nuova data non lo inviano; codice di uscita
del vecchio backup preservato. Sintassi dei sette file PowerShell verificata.
Questa prova non certifica DPAPI o la rete sul PC Windows.

I client inviano un POST HTTPS vuoto soltanto dopo una nuova copia con codice
0, non per controlli di integrità, esecuzioni saltate o singoli errori. Il
monitor vede IP/orario ma non riceve dati clinici, log, credenziali database o
contenuti degli archivi. URL univoci protetti nel Portachiavi Mac o con DPAPI
Windows, mai nel repository o nei job. Timeout breve, TLS verificato e nessun
reindirizzamento. Errori di consegna in `logs/monitor.json`, senza invalidare
il backup. Nessun reinvio di vecchi successi che sposti in avanti le 72 ore.
Il guasto del monitor può produrre un avviso prudenziale anche con backup
locale riuscito: confrontare sempre lo stato locale. Conservazione in avviso
(codice 2) non invia segnali: regola conservativa finché l'esito non torna 0.

Procedure: [Mac](../scripts/macos-backup/README.md#avviso-remoto-dopo-72-ore),
[Windows](../scripts/windows-backup/README.md#avviso-remoto-opzionale-dopo-72-ore--aggiornamento-22-ottobre).
Gate iniziale del monitor superato: nuovi export, segnali distinti ricevuti e
email tecnica consegnata e confermata. Verificare nel normale esercizio le
scadenze delle 21:00 Windows e delle 22:00 Mac; restano separati i collaudi
fisici dopo stop/riavvio e il restore dell'archivio reale Mac.

### Procedura storica OpenSSL Mac (non usare per i nuovi archivi age)

Le istruzioni seguenti e la vecchia sezione di preparazione descrivono lo stato
precedente a D-128, non quello operativo corrente riportato sopra. Il restore
OpenSSL è esclusivamente per file `.enc`; per `.age` seguire i pacchetti dedicati.

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

Programmare lo stesso comando ogni giorno alle 21:00 con `launchd`, usando
`StartCalendarInterval`, dopo la creazione del database Render. Il job non deve
contenere segreti: gli script li leggono dal Portachiavi. Se il Mac dorme,
l'esecuzione programmata viene recuperata al risveglio; se è spento non è
garantito il recupero prima della successiva scadenza. Prevedere un controllo
all'accesso e un nuovo tentativo quando rete e destinazioni sono disponibili.
Controllare data e checksum dell'ultimo file ogni mattina. Log e notifiche
automatiche vengono configurati insieme al database reale, senza registrare
l'URL di connessione.

### Ridondanza fisica confermata; automazione ancora da configurare

Aggiornamento del 21 ottobre 2026: il pacchetto Windows e le istruzioni sono in
[`scripts/windows-backup/README.md`](../scripts/windows-backup/README.md),
secondo D-127. Implementa configurazione locale protetta da DPAPI, cifratura age
autenticata, backup PostgreSQL, integrita, conservazione e verifica di decifratura.
Non installa job, non abilita connessioni Render e non configura notifiche email
o remote. Il nucleo ha superato il collaudo sintetico su macOS/PowerShell e
PostgreSQL temporaneo; ACL, DPAPI, TLS e pianificazione vanno verificati sul PC
Windows. Non equivale a un backup reale gia attivo. Il vecchio script macOS
OpenSSL mantiene il suo formato; non usarlo per decifrare archivi `.age`.

D-126 conferma per ora Mac e un computer Windows dedicato ai backup, collegato
a un'altra rete, senza introdurre il backup S3 proposto in chat. Il committente
ha confermato Windows 11 Pro 25H2, normalmente acceso e connesso. Entrambi usano
la memoria interna: non sono richiesti supporti USB. Restano da definire
percorsi, disponibilità del Mac e accessi sicuri.

Con le reti separate, la configurazione ora raccomandata è eseguire due backup
indipendenti direttamente da Render, uno su ciascun computer. Il secondo non
dipende così dall'accensione del Mac e non occorrono cartelle condivise o porte
aperte tra le due reti. Questo modifica la precedente proposta di replica dal
Mac, non un sistema già installato. Ogni macchina necessita di client PostgreSQL,
accesso sicuro al database e cifratura locale; preferire credenziali dedicate e
limitate, da autorizzare separatamente. Non salvare segreti nei file dei job.

Il Mac usa `launchd`; Windows dispone ora del pacchetto dedicato, ancora da
installare e configurare con Utilità di pianificazione, recupero delle esecuzioni
mancate e nuovi tentativi su errore. Lo script Bash macOS non è un job Windows.
Usare cartelle private non sincronizzate automaticamente in iCloud/OneDrive,
con cifratura del disco e del singolo archivio, conservazione e controllo dello
spazio su entrambe le destinazioni. Le copie devono essere datate e verificate,
non sincronizzate a specchio. Gli orari possono essere sfalsati ma non sono
ancora concordati. Il blocco automatico dell'applicazione non è richiesto.

Il pacchetto Windows implementa pubblicazione della cartella completata,
checksum, controllo dello spazio e verifica della copia entro 24 ore. Prima
di automatizzare restano il collaudo sul PC e la configurazione di tentativi
e monitoraggio degli errori. Non dichiarare riuscita la
ridondanza finché entrambe le destinazioni non sono verificate. Avvisi eseguiti
solo su un PC spento non possono notificare il guasto mentre è spento; il
controllo operativo dell'ultima copia resta necessario.

Le due reti non dimostrano da sole due sedi fisiche distinte. La password di
decifratura va conservata in modo recuperabile ma separato dai file. Due copie
online non equivalgono a una copia offline/immutabile; il PITR resta un livello
separato. Gli accessi di rete al database richiedono una verifica dedicata: il
Blueprint prevede `ipAllowList: []`; non aprire automaticamente PostgreSQL a
Internet per abilitare i due client. Con IP dinamici occorre concordare un
accesso controllato, non autorizzare indiscriminatamente tutti gli indirizzi.

Prima del GO servono un backup reale riuscito, la verifica delle copie e un
restore su un database isolato, con applicazione, scheduler, email e Calendar
disattivati finché non sia predisposto un ambiente di collaudo sicuro. Nessun
backup reale, accesso al Portachiavi o job è stato attivato con questa revisione
documentale o con la preparazione del pacchetto. Non sono autorizzate operazioni
su Calendar.

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

## PAZ-A2 — backfill identità Pazienti 2.0 (solo per database non vuoti)

> Stato operativo: PAZ-A2 è integrata e verificata con dati sintetici su SQLite
> e PostgreSQL. Non è mai stata eseguita su dati esterni e non va avviata sul
> database Render dichiarato vuoto: in quel caso PAZ-A3 deve chiudersi come
> preflight senza scritture, secondo D-117.

### Sicurezza dei database di test

La configurazione applicativa `testing` usa **sempre** `sqlite:///:memory:` e
ignora qualunque `DATABASE_URL` presente nella shell o nel file `.env`. Questa
regola è intenzionale: la suite principale usa `db.create_all()` e
`db.drop_all()` e non deve mai poter raggiungere un database esterno.

Il gate PostgreSQL PAZ-A2 usa una configurazione distinta, selezionata soltanto
dalla suite opt-in:

```bash
FLASK_ENV=paz_a2_postgres_testing \
PAZ_A2_TEST_DATABASE_URL='postgresql+psycopg://.../database_usa_e_getta' \
pytest -q tests/test_patient_a2_postgres.py
```

Regole obbligatorie:

- usare esclusivamente `PAZ_A2_TEST_DATABASE_URL`; non usare `DATABASE_URL` per
  questo gate;
- il database deve essere dedicato ai test e usa-e-getta;
- la suite deve verificare esplicitamente `postgresql` come dialetto e lo schema
  casuale atteso prima di migrazioni/apply;
- non usare mai database di sviluppo condiviso, staging o produzione;
- in assenza della variabile dedicata i test PostgreSQL A2 devono risultare
  skip, non ripiegare su un database ordinario.

### Gate prima di dry-run/apply

Prima di qualunque esecuzione A2 autorizzata su una copia controllata:

```bash
flask --app app db upgrade
flask --app app db check
pytest
pytest -q tests/test_patient_a2_postgres.py   # con database test dedicato

git diff --check
```

Verificare inoltre HEAD Git/build revision, head Alembic e che
`Appuntamento.persona_id`, `CallSonno.persona_id` e
`IscrizioneCorso.persona_v2_id` siano ancora tutti NULL.

### Dry-run e apply

Il dry-run è il comportamento predefinito e produce un piano firmato:

```bash
flask --app app patients backfill-identities \
  --dry-run \
  --plan-file /percorso/privato/paz-a2-plan.json \
  --report-file /percorso/privato/paz-a2-dry-run-report.json
```

L'apply richiede un piano esistente e valido:

```bash
flask --app app patients backfill-identities \
  --apply \
  --plan-file /percorso/privato/paz-a2-plan.json \
  --report-file /percorso/privato/paz-a2-apply-report.json
```

Non usare flag o procedure per aggirare firma, TTL, revisione codice, blocker,
fingerprint source/target o lock transazionale.

### Custodia e retention degli artefatti

Piano e report sono artefatti pseudonimi riservati:

- devono essere creati fuori da directory pubbliche e non vanno committati;
- il piano usa permessi `0600`, scrittura atomica e rifiuto dei symlink;
- piano e report non devono contenere nomi, CF, telefoni, email, note o altri
  valori identificativi in chiaro;
- il piano viene eliminato dopo un apply riuscito;
- se l'apply fallisce, conservare il piano solo per il tempo strettamente
  necessario alla diagnosi, con limite operativo iniziale di 24 ore;
- non includere questi artefatti nei backup ordinari o nella documentazione.

`SECRET_KEY` deve essere stabile e adeguata: una chiave effimera o troppo corta
blocca la produzione/applicazione di un piano verificabile.

### Errori, report e recovery post-commit

Gli errori dell'apply devono attraversare il confine CLI soltanto come codici
sanitizzati; non devono essere esposti messaggi SQL, statement, parametri o
catene di eccezioni contenenti PII.

Quando esiste già un piano valido, il failure report indica almeno `run_id`,
`error_code` e una fase stabile (`preflight`, `lock`, `revalidation`, `write` o
`audit`). Il report viene prodotto solo dopo il rollback della transazione di
backfill.

L'audit di successo è committato nella stessa transazione del backfill. Se,
dopo quel commit, falliscono esclusivamente la scrittura del report o la
cancellazione del piano, **non** tentare rollback del backfill già riuscito:

1. verificare l'evento di successo `pazienti_v2` e i conteggi minimizzati;
2. verificare lo stato DB con una nuova sessione;
3. rigenerare/conservare manualmente solo l'artefatto operativo necessario;
4. eliminare il piano quando la diagnosi è conclusa;
5. non rilanciare automaticamente lo stesso piano che prevedeva scritture:
   dopo un apply riuscito deve risultare `STALE_TARGET`.

### Confini della tranche

PAZ-A2 non deve:

- inferire `nome`/`cognome`;
- creare minori o `RelazionePersona`;
- copiare note legacy;
- deduplicare o fondere persone;
- valorizzare FK delle pratiche;
- modificare route/UI;
- eseguire cutover o cleanup legacy.

## PAZ-A3/A4 — preflight e cutover diretto sul database Render vuoto

Il deploy resta un'operazione separata e richiede approvazione esplicita. Il
controllo di database vuoto deve avvenire **prima** di qualunque migration A1/A4.
Il Blueprint di produzione/preproduzione esegue quindi il gate read-only come
prima operazione del `preDeployCommand`:

```bash
python patient_cutover_preflight.py --allow-applied
flask --app app db upgrade
flask --app app db check
flask --app app bootstrap-admin
```

Al primo cutover `patient_cutover_preflight.py` non importa `app.py`: legge
soltanto `alembic_version`, metadati dello schema e `COUNT(*)`, senza selezionare
né stampare PII e senza eseguire scritture. Accetta esclusivamente le revisioni
pre-A1 note della catena Render da `d91e6b4f2a30` a `c9e1f4a7b260`; lo schema
deve essere coerente con quella fase e i conteggi di anagrafiche, pratiche,
collegamenti e consensi devono essere tutti zero **prima** che `db upgrade` possa
partire.

`--allow-applied` non aggira il controllo del primo cutover. Serve soltanto a
rendere idempotente il hook nei deploy successivi: quando la revisione è già
`d4a7c2e9f610` o una revisione post-A4 esplicitamente riconosciuta, il gate
verifica che lo schema previsto per quella revisione sia completo e restituisce
`status: cutover_gia_applicato` senza pretendere che un database ormai in uso
torni vuoto. Il comando Flask `flask --app app patients preflight-cutover` resta
disponibile come controllo diagnostico stretto: a revisione A4 esegue anche i
conteggi e quindi segnala un database non vuoto.

Se la revisione non è ammessa, lo schema è inatteso, il preflight non è
eseguibile o anche un solo conteggio del primo cutover è diverso da zero:

1. interrompere il deploy/collaudo;
2. non eseguire automaticamente PAZ-A2 o altre scritture correttive;
3. identificare se i record sono sintetici o reali senza copiarli nei log;
4. decidere separatamente se svuotare il database di test oppure applicare il
   percorso controllato A2/A3 per un database da preservare.

Con preflight verde, il collaudo privato A4 usa esclusivamente dati sintetici e
verifica almeno:

- creazione, modifica, ricerca e scheda di una persona in Pazienti 2.0;
- collegamento di appuntamento, call sonno e iscrizione corso alle FK v2 in
  **tutti** i percorsi che portano una pratica allo stato confermato;
- stop esplicito e rollback se un codice fiscale identifica più anagrafiche
  attive;
- assenza di nuove righe in `persona_corso` e `collegamento_persona`;
- storico e consensi senza dati personali nei log;
- logout e pulsante Indietro del browser, con nuova autenticazione richiesta;
- resa e uso da tastiera dell'admin a 1440 px e 390 px.
- ricerca locale e Calendar con informativa sulla trasmissione del testo, risultati paginati e nessuna descrizione esterna resa nell’HTML;
- caricamento Calendar su richiesta nella scheda paziente, conferma e rifiuto manuali con CSRF e audit, unicità del collegamento, sola lettura delle anagrafiche archiviate e avviso esplicito per indisponibilità o risposta parziale;
- esclusione e coda operativa idempotente degli eventi creati dal sito ma rimasti privi di collegamento locale.

Al termine eliminare i record sintetici prima di qualunque uso reale. Dopo la
prima identità v2 non usare il downgrade Alembic A4: il rollback strutturale non
può ricostruire in modo sicuro lo stato applicativo successivo al cutover. Un
eventuale reset del database vuoto o un deploy correttivo richiedono una
decisione esplicita. PITR e backup cifrato restano obbligatori prima del primo
dato reale.

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

La sequenza corrente è in [PRE_GO_LIVE_CHECKLIST.md](PRE_GO_LIVE_CHECKLIST.md). Al primo cutover il preflight deve sempre precedere `db upgrade`; con schema A4 già applicato non si richiede un nuovo database vuoto. I controlli seguenti restano riferimenti tecnici, non una riapertura del lavoro PayPal sospeso.

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
