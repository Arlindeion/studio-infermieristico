# Operatività tecnica

Ultimo aggiornamento: 29 luglio 2026.

## Architettura

- Applicazione Flask monolitica in `app.py`.
- Rendering server-side con Jinja2.
- SQLAlchemy ORM; SQLite locale e PostgreSQL in produzione.
- JavaScript vanilla esternalizzato per rispettare la Content Security Policy.
- Flask-Login per l'area admin.
- Flask-Mail per le notifiche.
- Flask-Limiter per i limiti di richiesta.
- Flask-Talisman per gli header di sicurezza.
- APScheduler per i promemoria.
- Google Calendar come collante con Arzamed.

Non introdurre framework frontend, SQL grezzo o dipendenze non necessarie.

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
| Produzione | Render Web Service Starter o superiore, Francoforte | Render PostgreSQL Basic-256mb o superiore, Francoforte | dominio definitivo definito in D-027 | pubblico dopo il gate pre-lancio |

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
All'avvio Render esegue nell'ordine `flask db upgrade`, il comando sicuro
`bootstrap-admin` e infine Gunicorn. I comandi preparatori disabilitano lo
scheduler; il processo Gunicorn lo avvia una sola volta perché usa un worker.

`render.production.yaml` prepara un secondo Blueprint con nomi distinti. Non è
il file del Blueprint esistente e non viene scoperto o sincronizzato
automaticamente. Dichiara piani a pagamento: non va selezionato nel pannello,
validato tramite un'operazione che crei risorse o sincronizzato senza un nuovo
ordine esplicito successivo alla presentazione del costo aggiornato.

Il file è intenzionalmente sicuro per la prima accensione:

- usa `main`, che prima della creazione deve essere portato esattamente al
  commit approvato e nuovamente verificato;
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
- usa un pre-deploy separato per migrazioni e bootstrap, lasciando a Gunicorn
  il solo avvio dell'applicazione.

Il JSON Google non è rappresentato nel Blueprint. Prima del collaudo reale va
caricato direttamente come secret file con nome
`google-calendar-service-account.json`; Render lo monta in
`/etc/secrets/google-calendar-service-account.json`. Nessun valore segreto va
inserito nel repository.

### Gate delle risorse di produzione separate

La sequenza seguente è obbligatoria e non può essere anticipata:

1. ottenere un ordine esplicito per generare costi Render;
2. rileggere dal pannello costo totale, metodo di pagamento e piani selezionati;
3. portare `main` al commit verificato senza modificare la storia pubblicata;
4. creare il Blueprint da `render.production.yaml` senza dominio e con
   configurazione privata;
5. inserire i segreti direttamente nel pannello e caricare il secret file;
6. verificare database vuoto, migrazioni, admin, Basic Auth, `noindex`,
   `/healthz` e assenza di dati reali;
7. ottenere autorizzazioni separate prima di email reali e scritture Calendar;
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
| `GOOGLE_CALENDAR_ICS_URL` | Lettura del calendario condiviso con Arzamed | Sì |
| `CALENDARIO_CACHE_SECONDI` | Durata cache calendario, default 300 | No |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Percorso della credenziale di scrittura | Sì |
| `GOOGLE_CALENDAR_ID` | Calendario su cui scrivere | Sì |
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

Nello staging iniziale non inserire credenziali SMTP, Calendar reale, URL iCal
o Analytics. I dati sono esclusivamente fittizi. Dopo il primo login riuscito,
rimuovere `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD`, salvare e
ridistribuire; `bootstrap-admin` verificherà l'account già presente.

### Preproduzione privata con integrazioni reali

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

Senza l'opt-in esplicito lo staging continua a richiedere
`MAIL_SUPPRESS_SEND=true`; il Blueprint gratuito corrente resta quindi incapace
di inviare email per errore. `flask --app app validate-config` verifica anche
server `smtp.mail.ovh.net`, porta 587, TLS attivo, SSL disattivo, casella
mittente approvata e presenza del secret file Google, senza mostrare valori
sensibili.

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
| `MAIL_ADMIN_RECIPIENT` | indirizzo interno scelto dall'attività |
| `GOOGLE_CALENDAR_ICS_URL` | URL iCal segreto di lettura |
| `GOOGLE_CALENDAR_ID` | identificativo del calendario operativo |
| secret file `google-service-account.json` | JSON caricato dal pannello, disponibile in `/etc/secrets/` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `/etc/secrets/google-service-account.json` |
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
errore, non indirizzi dei destinatari. Non inserire mai URL iCal, token,
password, contenuto dei questionari o dati identificativi nei log.

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

Le regole di prodotto e i conteggi posti sono descritti in `SITE_MAP_AND_FLOWS.md`.

## Stati

- Appuntamenti: `In attesa`, `Confermato`, `Annullato`.
- Call sonno: `In attesa`, `Confermata`, `Annullata`, `Conclusa`.
- Iscrizioni corso: `Nuova`, `Contattato`, `Confermato`, `Annullato`.
- Corsi: `Aperto`, `Completo`, `Chiuso`, `Annullato`, `Concluso`.
- Percorsi nascita: `Bozza`, `Aperto`, `Chiuso`, `Concluso`.

Le richieste corso senza data usano `tipo_richiesta = ricontatto`, mostrato in admin come `Da ricontattare`; non è uno stato aggiuntivo. Conservano il normale stato iniziale `Nuova`, occupano zero posti e proseguono poi negli stati corso già elencati. Il modulo unico della homepage registra anche la tematica scelta senza richiedere i dati amministrativi di un'iscrizione.

## Google Calendar e Arzamed

- Lettura: `GOOGLE_CALENDAR_ICS_URL` permette di conoscere impegni e chiusure segnati sul calendario sincronizzato da Arzamed.
- Cache: controllata da `CALENDARIO_CACHE_SECONDI`.
- Scrittura: un account di servizio crea o aggiorna eventi quando appuntamenti o corsi vengono confermati; le call sonno vengono invece inserite subito come provvisorie per bloccare lo slot anche in Arzamed.
- Gli eventi creati in Arzamed espongono su Google Calendar inizio e fine
  effettivi, che il sito usa integralmente per rilevare i conflitti. Una
  richiesta sanitaria dal sito blocca inizialmente 30 minuti; prima di
  confermarla l'admin deve scegliere la durata effettiva, da 1 a 480 minuti. Il
  valore viene salvato in `Appuntamento.duration_minutes` e
  determina conflitti, disponibilità e fine dell'evento Calendar.
- L'account di servizio deve avere sul calendario soltanto i permessi necessari.
- Un conflitto con un evento Calendar impedisce la conferma di quell'intervallo,
  ma non elimina la richiesta: l'admin riceve un avviso e può modificarla. Un
  errore secondario durante la successiva scrittura Calendar non annulla invece
  la conferma già salvata.

## Errori parziali

Il dato principale ha priorità:

- una prenotazione non deve andare persa se l'email fallisce;
- un'iscrizione non deve andare persa se Calendar fallisce;
- un corso non deve scomparire per un errore di sincronizzazione.

Dopo il salvataggio, gli errori secondari devono essere registrati in `RegistroEvento`. Quando l'errore riguarda un'azione admin, mostrare un avviso comprensibile senza fingere che l'intera operazione sia fallita.

## Sicurezza

- CSRF manuale tramite `_csrf_token` di sessione; verificare ogni nuovo form che modifica dati.
- Rate limiting almeno su prenotazione e login.
- Cookie sicuri in produzione.
- Nessun segreto hardcoded.
- Nessun dato personale nei log oltre ciò che è realmente necessario.
- Confermare che la CSP autorizzi soltanto origini indispensabili.
- Proteggere route private e admin con autenticazione e controllo degli identificativi.

### Credenziale admin iniziale

Non esistono credenziali predefinite. In locale il primo amministratore si crea
con `flask --app app create-admin`, che richiede una password di almeno 16
caratteri. Su un database di produzione vuoto l'avvio richiede entrambe le
variabili `ADMIN_BOOTSTRAP_USERNAME` e `ADMIN_BOOTSTRAP_PASSWORD`; se una manca,
l'applicazione si arresta. Dopo il primo accesso riuscito, rimuovere entrambe le
variabili dal gestore dei segreti: l'account resta nel database e gli avvii
successivi non ne dipendono.

## Database e migrazioni

La baseline Alembic `56dda7f5137f` crea l'intero schema; la revisione corrente è
`4d8b2c7a91e6`: le revisioni successive aggiungono qualificazione, UTM e stato
dei promemoria email alla call sonno, rimuovono i campi del precedente
promemoria WhatsApp e aggiungono la durata effettiva agli appuntamenti. Un nuovo
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

La baseline è stata verificata generando anche SQL PostgreSQL e con prove
automatiche di upgrade ripetuto su database vuoto e adozione di uno schema
rappresentativo popolato. Non usare `db.create_all()` per database operativi.

## Backup e ripristino PostgreSQL

### Livelli di protezione

1. **Render PITR:** obbligatorio prima dei dati reali. Sul workspace Hobby il database PostgreSQL a pagamento conserva una finestra point-in-time di 3 giorni. Un ripristino genera un nuovo database da verificare prima di cambiare `DATABASE_URL`.
2. **Export logico locale:** `scripts/backup_postgres.sh` esegue ogni giorno `pg_dump` in formato custom, cifra il dump con AES-256 e PBKDF2, genera SHA-256 e conserva la copia sul PC dell'attività.
3. **Export Render manuale:** creare un export dalla sezione Recovery prima di migrazioni rischiose o interventi straordinari; Render conserva questi export per 7 giorni, quindi scaricarli se devono durare più a lungo.

Il database gratuito è ammesso soltanto nello staging con dati fittizi: scade
dopo 30 giorni e non offre PITR o export gestiti. Prima dell'apertura pubblica
va aggiornato al piano pagato.

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
- GA4 caricato solo dopo consenso.
- Privacy, cookie e policy operative validate.
- Log controllati e privi di dati personali superflui.
- Nome del logo normalizzato in `static/img/logo.png` e coerente con i riferimenti applicativi sui filesystem Linux case-sensitive.
- Controllo visivo desktop/mobile completato.

## Dati esclusi dalla documentazione

Non aggiungere a `docs/`:

- contenuto di `.env`;
- database o backup reali;
- JSON degli account di servizio;
- URL iCal;
- elenchi iscritti, pazienti o partecipanti;
- feedback non anonimizzati o prove di consenso.
