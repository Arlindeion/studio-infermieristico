# Area Pazienti 2.0 — specifica corrente e registro di revisione

> **Stato al 10 settembre 2026:** PAZ-A1, PAZ-A2 v5 e PAZ-A4 sono integrate e verificate localmente nel branch `codex/pazienti-2-0`; il cutover diretto è approvato in D-117. Nessun deploy o uso di dati reali è autorizzato da questo documento.
>
> Le sezioni 1–38 conservano specifiche e registro delle revisioni A1/A2. Lo stato storico riportato dentro quelle sezioni descrive i pacchetti al momento delle singole review; non prevale sul presente riepilogo operativo.
>
> Integrazione corrente: PAZ-A1 `e35fe65`, PAZ-A2 `9213d52`, aggiornamento roadmap `4276c1f`, PAZ-A4 `7e022bf`. La suite integrata corrente ha superato 410 test Python, 37 test JavaScript, 6 test PostgreSQL opt-in e i controlli Alembic SQLite/PostgreSQL. Queste evidenze locali non equivalgono a un deploy.

## 1. Regole di stato e fonti canoniche

Gli stati ammessi per una tranche sono:

`Proposta → In revisione → Approvata per lo sviluppo → Implementata localmente → Verificata → Deployata`

Una patch allegata non equivale a una modifica applicata.

Finché PAZ-A1 resta `In revisione`:

- non modificare `docs/ROADMAP.md` o `docs/DECISIONS.md` per dichiararla approvata/implementata;
- non modificare `docs/OPERATIONS.md` salvo che cambi davvero una procedura operativa approvata;
- non eseguire backfill;
- non popolare le nuove FK;
- non modificare route o UI per usare il nuovo modello;
- non eseguire deploy o migrazioni su staging/produzione.

Le proposte storiche in `docs/proposte/` restano materiale di riferimento, non istruzioni operative.

## 2. Obiettivo di PAZ-A1

PAZ-A1 introduce soltanto le fondamenta additive del futuro modello anagrafico.

### In scope

- `Persona`;
- `RecapitoPersona`;
- `RelazionePersona`;
- storage minimo di `SegnalazioneDuplicato`;
- header auditabile di `FusionePersona`;
- `Appuntamento.persona_id` nullable;
- `CallSonno.persona_id` nullable;
- `IscrizioneCorso.persona_v2_id` nullable e transitorio;
- validazione/normalizzazione riutilizzabile;
- vincoli e test dello schema;
- diagnostica per dimostrare che i flussi legacy non scrivono sulle nuove FK.

### Fuori scope

- backfill `PersonaCorso → Persona`;
- deduplicazione reale;
- fusione reale;
- fingerprint/soppressione `non_unire` basata sui dati;
- payload di rollback della fusione;
- anonimizzazione di `Persona`;
- modifica di `Admin → Pazienti`;
- cartella infermieristica, documenti, consensi v2 e promemoria;
- cutover e ritiro del legacy.

## 3. Decisioni correnti della candidata v4

### PAZ-A1.1 — schema esclusivamente additivo

La migrazione candidata non rimuove né rinomina strutture legacy.

Restano fonti di verità:

- `PersonaCorso`;
- `CollegamentoPersona`;
- `ConsensoPrivacyPaziente`;
- `IscrizioneCorso.persona_id → PersonaCorso`.

Le nuove FK sono nullable e devono restare vuote in A1.

### PAZ-A1.2 — mapping legacy con FK temporanea

`Persona.legacy_persona_corso_id` è:

- nullable;
- UNIQUE;
- FK verso `persona_corso.id`;
- `ON DELETE RESTRICT`.

Questo impedisce un mapping orfano durante la migrazione. La FK verrà rivalutata soltanto al cleanup legacy.

### PAZ-A1.3 — lifecycle `Persona` ristretto a ciò che A1 può garantire

Stati ammessi in A1:

- `attiva`;
- `archiviata`;

Regola DB bidirezionale:

- `archiviata` richiede `archiviato_il IS NOT NULL`;
- `attiva` richiede `archiviato_il IS NULL`.

Anche lo stato `fusa` è rimandato alla tranche che implementerà la fusione reale: A1 non può garantire la coerenza tra stato della persona, record `FusionePersona` e spostamenti effettuati.

La candidata v2 esponeva anche `anonimizzata`, ma un `CHECK` sulla sola `persona` non può garantire l'eliminazione/minimizzazione dei recapiti e degli altri record collegati. Per evitare una falsa garanzia:

- `anonimizzata` non è uno stato valido in PAZ-A1 v4;
- `Persona.dati_anonimizzati_il` non viene creato in A1;
- anonimizzazione e relativa transazione multi-tabella verranno progettate nella tranche che introduce realmente la funzione.

### PAZ-A1.4 — recapiti senza hard delete ordinario

`Persona.recapiti` non usa `delete-orphan`.

`RecapitoPersona.persona_id` usa FK `RESTRICT`.

Vincoli:

- tipo `telefono` o `email`;
- UNIQUE `(persona_id, tipo, valore_normalizzato)`;
- un recapito archiviato non può restare principale;
- al massimo un recapito attivo principale per persona/tipo tramite indice univoco parziale.

L'archiviazione è il percorso applicativo previsto; A1 non introduce route di eliminazione.

### PAZ-A1.5 — relazioni e referenti

Ruoli descrittivi iniziali:

- madre;
- padre;
- tutore;
- affidatario;
- caregiver;
- altro.

`caregiver` non conferisce automaticamente poteri di consenso o rappresentanza.

Il DB impedisce:

- autorelazioni;
- duplicazione della stessa relazione/ruolo;
- più `contatto_principale` attivi per la stessa persona assistita;
- più `referente_comunicazioni` attivi per la stessa persona assistita;
- relazione archiviata con flag operativi ancora attivi.

Più `referente_consensi` restano tecnicamente ammessi, ma nessuna route A1 usa il flag per autorizzare azioni.

### PAZ-A1.6 — normalizzazione separata dalla validazione

Il modulo `patient_data.py` è indipendente da Flask/SQLAlchemy ed è riusabile dal futuro backfill.

Regole:

- nomi: Unicode NFKC, trim e spazi ripetuti ridotti; nessuna alterazione automatica di apostrofi/trattini/case;
- CF: NFKC, spazi rimossi, uppercase, limite di lunghezza; nessuna validazione formale del CF in A1;
- email: trim/casefold, forma minima email e limiti;
- telefono: solo formattazione prevista, lettere rifiutate, nessun `+39` aggiunto automaticamente.

Per il prefisso internazionale `00`, il prefisso viene rimosso **prima** del controllo del limite di 15 cifre. Quindi un numero con 15 cifre effettive dopo `00` è accettato.

### PAZ-A1.7 — anonimizzazione, deduplicazione e fusione non vengono simulate con JSON non validabile

La v2 conteneva:

- `SegnalazioneDuplicato.motivi` JSON;
- `fingerprint` HMAC;
- `FusionePersona.dettagli` JSON.

Gli eventi ORM potevano validare questi campi, ma SQL diretto e bulk potevano aggirare tale validazione; inoltre il DB non può verificare che una stringa di 64 caratteri sia realmente un HMAC prodotto con la chiave applicativa.

La v4 mantiene questi campi fuori da A1.

`SegnalazioneDuplicato` conserva soltanto:

- coppia ordinata di persone;
- livello;
- timestamp.

Gli stati `non_unire`/`fuso`, la decisione, i motivi e il fingerprint sono rimandati al workflow di deduplicazione: senza fingerprint non sarebbe corretto rendere persistente una soppressione `non_unire`.

`FusionePersona` conserva soltanto l'header di una fusione futura già conclusa con successo:

- persona principale;
- persona secondaria;
- `operazione_id` UNIQUE;
- stato;
- `applicata_il`;
- `annullata_il`;
- `admin_id` obbligatorio.

Il dettaglio dei motivi/fingerprint e dei record spostati verrà introdotto con il workflow effettivo, usando una struttura che possa essere validata end-to-end e testata in concorrenza.

La funzione `validate_merge_details` non fa più parte di A1; di conseguenza scompare anche il bug v2 per cui `True` era accettato come `int` in `record_ids`.

### PAZ-A1.8 — parità ORM/Alembic

La v4 allinea esplicitamente nomi e semantica tra metadata e migration:

- `fk_appuntamento_persona_v2` — `ON DELETE RESTRICT`;
- `fk_call_sonno_persona_v2` — `ON DELETE RESTRICT`;
- `fk_iscrizione_corso_persona_v2` — `ON DELETE RESTRICT`;
- FK delle nuove tabelle con nomi espliciti;
- indici di `RelazionePersona` e `FusionePersona` con gli stessi nomi della migration;
- UNIQUE esplicite per mapping legacy e `operazione_id`.

La verifica in copia isolata non rileva drift su SQLite o PostgreSQL. Il controllo deve essere ripetuto dopo l'integrazione nel checkout reale perché HEAD Git, head Alembic o modelli potrebbero essere cambiati.

Su SQLite le tre FK nullable verso `persona` vengono aggiunte come colonne inline tramite `ALTER TABLE`, evitando il recreate delle tabelle legacy referenziate. Alembic/SQLAlchemy non riflette nome e opzione `ON DELETE` di queste FK inline: `migrations/env.py` esclude dal confronto soltanto le tre firme note, mentre test dedicati verificano direttamente con `PRAGMA foreign_key_list` target, colonna e `ON DELETE RESTRICT`, oltre a una scrittura non valida.

## 4. Collegamenti alle pratiche e fonte di verità

| Fase | Fonte di verità pratiche | FK v2 |
|---|---|---|
| PAZ-A1 | solo legacy | create, sempre NULL |
| PAZ-A2 | legacy | identità/recapiti popolati, pratiche ancora NULL |
| PAZ-A3 | legacy + confronto | no-op se i conteggi del database Render sono nulli; altrimenti stop e nuova review |
| PAZ-A4 | v2 per ogni nuova scrittura | cutover diretto, senza dual-write; lettura legacy solo per compatibilità |
| PAZ-A5 | v2 dopo cutover | legacy ritirabile solo dopo riconciliazione |

Non sono ammessi collegamenti per somiglianza di nome.

## 5. Migrazione candidata

File candidato:

`migrations/versions/8f2c7d1e4a90_schema_pazienti_v2_paz_a1.py`

Nel pacchetto revisionato il parent osservato è:

`c9e1f4a7b260`

L'ID e il `down_revision` non sono definitivi finché non vengono verificati nel checkout Git corrente. Se esistono più head Alembic, occorre prima risolvere consapevolmente il grafo.

### Downgrade

Il downgrade A1 è considerato sicuro soltanto **prima di qualunque backfill/scrittura significativa v2**.

Dopo A2/A3 il rollback previsto è applicativo e conservativo, non la cancellazione automatica delle nuove tabelle.

## 6. Test della candidata v4

### 6.1 Test specifici eseguibili senza Flask

File:

- `tests/test_patient_data.py`;
- `tests/test_patient_a1_schema.py`.

Coprono:

- normalizzazione nomi/CF/email/telefono;
- rifiuto input malformati;
- prefisso `00` con limite applicato alle cifre effettive;
- sesso anagrafico e ruoli;
- upgrade completo della catena Alembic su SQLite;
- conservazione di un grafo legacy popolato con `QuestionarioSonno`, `AutorizzazioneImmagini` e `PresenzaAccompagnamento`;
- nuove FK inizialmente NULL;
- lifecycle `Persona` bidirezionale;
- stato `anonimizzata` non ammesso in A1;
- assenza di `dati_anonimizzati_il` su `Persona` A1;
- vincoli recapiti e referenti principali;
- FK legacy `RESTRICT`;
- assenza di JSON/fingerprint nelle tabelle duplicato/fusione;
- storage duplicati ridotto a coppia/livello, senza decisioni o payload privacy-sensitive;
- coerenza stato/admin delle fusioni;
- downgrade pre-backfill e nuovo upgrade;
- presenza coerente dei nomi FK/indici tra sorgente ORM e migration;
- guardia AST ampliata contro scritture sulle FK v2 tramite costruttori, assignment, `setattr`, update/bulk e SQL evidente.

Evidenza finale ottenuta su copia isolata della base `ebab09b`, con PostgreSQL reale configurato:

```text
PAZ_A1_POSTGRES_URL='postgresql+psycopg://...' pytest -q
329 passed
```

La suite comprende upgrade/downgrade SQLite con FK attive, i tre test PostgreSQL e i quattro test applicativi resi indipendenti dalla data del calendario.

### 6.2 Test PostgreSQL reale aggiunto

Nuovo file:

`tests/test_patient_a1_postgres.py`

È opt-in e richiede:

`PAZ_A1_POSTGRES_URL=<database PostgreSQL di test usa-e-getta>`

Il test:

1. crea uno schema isolato casuale;
2. esegue l'intera catena Alembic fino ad A1;
3. prova una FK `RESTRICT` reale;
4. prova l'indice univoco parziale dei recapiti principali;
5. esegue due transazioni concorrenti e verifica che non possano entrambe creare un recapito principale attivo dello stesso tipo;
6. elimina lo schema di test a fine sessione.

Evidenza finale su PostgreSQL 18.4 locale, database sintetico e schema casuale:

```text
pytest -q tests/test_patient_a1_postgres.py
3 passed
```

I due test dei vincoli usano `pytest.raises(IntegrityError)` all'esterno del savepoint, consentendo a SQLAlchemy di effettuare il rollback corretto. Il test concorrente identifica il PID del secondo writer e attende in `pg_stat_activity` che risulti realmente bloccato su un lock prima di autorizzare il commit del primo writer.

### 6.3 Controllo AST

La v2 controllava soltanto keyword nei costruttori. La v3 ha ampliato la guardia e la v4 la mantiene:

- assegnazioni dirette sulle variabili note delle pratiche;
- `setattr`;
- mapping usati da update/bulk;
- SQL letterale `INSERT/UPDATE` evidente.

Il controllo resta una guardia regressiva statica, non una prova formale contro scrittura dinamica/alias arbitrari.

## 7. Matrice dei rilievi v2 → v4

| Rilievo revisione v2 | Stato v4 |
|---|---|
| Drift FK `ondelete` ORM/migration | corretto; `db check` passa su PostgreSQL e SQLite |
| Nomi indici diversi | corretto; `db check` passa su PostgreSQL e SQLite |
| `Persona` attiva con timestamp archiviazione | bloccata da CHECK bidirezionale |
| stato `fusa` senza workflow transazionale | rimandato insieme alla fusione reale |
| anonimizzazione non realmente garantita | funzione/stato rimandati fuori da A1 |
| PostgreSQL solo compilato offline | risolto: 3 test reali passati, inclusa concorrenza osservata su lock |
| AST solo costruttori | controllo ampliato |
| JSON motivi/dettagli aggirabile via SQL | JSON rimossi da A1 |
| fingerprint HMAC arbitrario via SQL | fingerprint rimandato al workflow deduplica |
| `True` accettato come record ID | funzione/payload rimossi da A1 |
| prefisso `00` conteggiato prima del limite | corretto e testato |
| documento mescolava v1/v2 e problemi aperti/chiusi | documento consolidato; storico separato |

## 8. Chiusura dei P0/P1 della candidata A1

### Risolto — parità ORM/Alembic

Su database sintetici SQLite e PostgreSQL è stato eseguito:

```bash
flask --app app db upgrade
flask --app app db check
```

Esito: `No new upgrade operations detected.`

### Risolto — migration SQLite con dati legacy collegati

La v3 ricreava `call_sonno` e `iscrizione_corso` tramite batch mode, causando `FOREIGN KEY constraint failed` con righe figlie. La v4 aggiunge e rimuove le colonne nullable senza ricreare le tabelle su SQLite.

Il test ora popola e conserva in upgrade e downgrade pre-backfill:

- `CallSonno → QuestionarioSonno`;
- `IscrizioneCorso → AutorizzazioneImmagini`;
- `IscrizioneCorso → PresenzaAccompagnamento`;
- `PersonaCorso` e `Appuntamento`.

`PRAGMA foreign_key_check` resta vuoto e le tre nuove FK risultano `ON DELETE RESTRICT`.

### Risolto — PostgreSQL reale e concorrenza

```bash
PAZ_A1_POSTGRES_URL='postgresql+psycopg://...' \
pytest -q tests/test_patient_a1_postgres.py
```

Esito: `3 passed`, senza skip. I test di errore effettuano rollback al savepoint e la contesa del secondo writer è osservata esplicitamente prima del commit del primo.

### Risolto — suite applicativa con clock controllato

I quattro test che usavano le date fisse `1–2 settembre 2026` calcolano ora un martedì futuro e il giorno successivo. La suite completa passa con `329 passed`.

Non risultano P0 o P1 tecnici aperti nella candidata v4 rispetto al perimetro A1. Questo non autorizza automaticamente applicazione, A2, backfill o deploy.

## 9. Criteri per passare a “Implementata localmente”

PAZ-A1 può cambiare stato soltanto quando:

1. esiste approvazione esplicita allo sviluppo/applicazione della tranche;
2. HEAD Git e head Alembic sono verificati nel checkout reale;
3. la migration candidata è eventualmente re-parentata/rigenerata;
4. `flask --app app db check` passa;
5. test specifici SQLite passano;
6. test PostgreSQL reali passano, inclusa la concorrenza;
7. suite applicativa non presenta regressioni A1 e i test dipendenti dalla data sono resi deterministici o formalmente separati con issue/tranche dedicata;
8. `git diff --check` passa;
9. il diff viene revisionato manualmente;
10. nessun dato reale è stato usato e nessun deploy è stato eseguito.

## 10. Sequenza dopo A1

Solo dopo accettazione A1:

### PAZ-A2 — backfill identità

- dry-run obbligatorio;
- mapping idempotente `PersonaCorso → Persona`;
- nessuna separazione irreversibile nome/cognome;
- recapiti creati senza fusione tra persone;
- nessun minore creato da `nome_bambino`/`eta_bambino`;
- nessuna pratica collegata alle FK v2.

### PAZ-A3 — collegamento pratiche

- mapping verificato soltanto per ID legacy;
- confronto con `CollegamentoPersona`;
- stop su ambiguità;
- report minimizzato.

### PAZ-A4 — UI/cutover controllato

D-117 approva il cutover diretto: tutte le nuove anagrafiche e associazioni usano il modello v2, senza dual-write. Il legacy resta presente ma non riceve nuovi record.

### PAZ-A5 — cleanup legacy

Solo dopo finestra di stabilizzazione, backup/restore testato e approvazione separata.

## 11. Storico sintetico delle revisioni

### v1 — prototipo iniziale

Punti positivi: schema additivo, conservazione legacy, nessuna fusione automatica.

Problemi principali: `delete-orphan`, validazione recapiti insufficiente, JSON implicito, semantica fusioni incompleta, test insufficienti e aggiornamenti canonici prematuri.

### v2 — prima hardening

Ha corretto: stato documentale, `delete-orphan`, mapping legacy, principali concorrenti, validazione di base, admin fusioni, payload JSON minimizzati.

La revisione successiva ha rilevato: drift ORM/Alembic, lifecycle `Persona`, assenza PostgreSQL reale, AST incompleto, bypass SQL/bulk dei JSON/HMAC, bug `bool` negli ID, bug telefono `00` e documento non consolidato.

### v3 — seconda hardening

Ha ridotto il perimetro A1 e corretto il drift ORM/Alembic, ma falliva su SQLite con dati figli legacy. Due test PostgreSQL gestivano male i savepoint e il test concorrente non dimostrava la contesa.

### v4 — candidata corrente

Corregge la migration SQLite senza rebuild delle tabelle referenziate, i savepoint PostgreSQL, la sincronizzazione concorrente e i test dipendenti dalla data. Tutti i gate tecnici A1 passano in copia isolata: `329 passed`, `db check` verde su SQLite e PostgreSQL, `git diff --check` verde.

## 12. Regole di handoff

Ogni successiva AI/revisore deve:

1. verificare il checkout reale aggiornato, applicando la candidata per revisione soltanto a una copia isolata finché non viene autorizzata l'integrazione;
2. leggere `AGENTS.md`, `docs/README.md` e questo documento;
3. controllare `git status`, HEAD Git e head Alembic;
4. non applicare automaticamente patch/allegati;
5. non sovrascrivere modifiche locali non attribuite;
6. mantenere separate schema, backfill, collegamenti, UI, cutover e deploy;
7. riportare esattamente comandi/test eseguiti e quelli non eseguiti;
8. non dichiarare risolto un P0 sulla sola base di ispezione statica;
9. usare database sintetici usa-e-getta per le prove; non usare dati reali senza autorizzazione separata;
10. aggiornare le fonti canoniche solo quando lo stato effettivo lo giustifica.

## 13. Prossima azione consentita

La prossima azione prima di A2 è integrare PAZ-A1 v4 nel checkout reale, previa conferma della base `ebab09b` o re-parenting consapevole, quindi ripetere:

1. `flask db upgrade` e `flask db check` su database sintetici;
2. suite completa con PostgreSQL opt-in;
3. revisione del diff e commit A1 separato;
4. nessun A2 finché A1 non è integrata e verificata nel repository.

Non sono ancora autorizzati A2, backfill, commit/push, deploy o aggiornamenti dei database esterni.

---

## 14. PAZ-A2 — proposta di progettazione del backfill identità

> **Stato:** `Proposta revisionata v2`.
>
> Questa sezione progetta PAZ-A2 in anticipo, ma non la autorizza. Restano validi i gate della sezione 13: A2 non può essere eseguita finché PAZ-A1 non è integrata e verificata nel checkout reale.
>
> La revisione del 7 settembre 2026 ha corretto integrità del piano, race tra verifica e apply, cancellazione dei recapiti dopo anonimizzazione, lock cross-database, audit transazionale e identificazione della build/ambiente. Nessun codice A2 è stato applicato.

### 14.1 Obiettivo

PAZ-A2 popola esclusivamente le identità e i recapiti del nuovo modello a partire da `PersonaCorso`, mantenendo il legacy come fonte di verità.

Il risultato atteso è un mapping deterministico e verificabile:

`PersonaCorso.id → Persona.legacy_persona_corso_id`

PAZ-A2 non collega ancora appuntamenti, call sonno o iscrizioni corso alle nuove FK.

### 14.2 In scope

PAZ-A2 può:

- creare una `Persona` per ogni `PersonaCorso`;
- aggiornare una `Persona` già mappata quando il nuovo modello è ancora sotto proprietà esclusiva del backfill;
- valorizzare `legacy_persona_corso_id`;
- conservare il nome completo legacy in `legacy_nome_completo`;
- copiare il codice fiscale dopo la normalizzazione prevista da A1;
- creare/aggiornare/archiviare `RecapitoPersona` per telefono ed email validi;
- propagare in modo sicuro l'anonimizzazione già avvenuta nel legacy senza ricreare o conservare identificativi nel target;
- produrre dry-run, piano applicabile e report minimizzati;
- rilevare collisioni e anomalie senza deduplicare o fondere;
- essere ripetuta in modo idempotente prima di A3.

### 14.3 Fuori scope

PAZ-A2 non deve:

- valorizzare `Persona.nome` o `Persona.cognome`;
- inferire nome/cognome dividendo `PersonaCorso.nome`;
- creare `RelazionePersona`;
- creare minori da `nome_bambino` o `eta_bambino`;
- copiare `PersonaCorso.note`;
- creare `SegnalazioneDuplicato`;
- creare `FusionePersona`;
- deduplicare persone;
- popolare `Appuntamento.persona_id`;
- popolare `CallSonno.persona_id`;
- popolare `IscrizioneCorso.persona_v2_id`;
- migrare consensi;
- modificare route, template o UI;
- modificare o anonimizzare direttamente `PersonaCorso`;
- eseguire cutover o cleanup legacy.

---

## 15. PAZ-A2.1 — il backfill non è una migration Alembic

PAZ-A2 non deve essere implementata come data migration dentro una nuova revisione Alembic.

Motivi:

- il dry-run deve essere obbligatorio e leggibile prima della scrittura;
- il processo deve essere ri-eseguibile;
- deve produrre un report strutturato;
- deve poter fermarsi su blocker senza lasciare una migration Alembic in stato ambiguo;
- deve supportare un successivo delta-backfill;
- la durata e la logica di bonifica dei dati non devono essere accoppiate al cambio di schema.

A2 viene quindi implementata come **servizio applicativo + comando CLI esplicito**.

Struttura proposta:

- `patient_backfill.py` — trasformazioni, piano, report e orchestrazione testabile;
- `app.py` — sola registrazione del comando CLI e passaggio esplicito di sessione/modelli;
- `tests/test_patient_a2_backfill.py` — test funzionali cross-database;
- `tests/test_patient_a2_postgres.py` — lock/concorrenza e comportamento PostgreSQL reale.

Nessuna nuova migration è prevista per A2 se la specifica non introduce nuovi campi.

---

## 16. PAZ-A2.2 — proiezione deterministica `PersonaCorso → Persona`

### 16.1 Record legacy attivo

Per un `PersonaCorso` con `dati_anonimizzati_il IS NULL`:

| Campo `Persona` | Regola A2 |
|---|---|
| `legacy_persona_corso_id` | ID legacy, obbligatorio |
| `legacy_nome_completo` | `normalize_patient_name(PersonaCorso.nome)` |
| `nome` | `NULL` |
| `cognome` | `NULL` |
| `codice_fiscale` | `normalize_tax_code(...)`, se memorizzabile |
| `data_nascita` | `NULL` |
| `sesso_anagrafico` | `NULL` |
| luogo/residenza | tutti `NULL` |
| `stato` | `attiva` |
| `archiviato_il` | `NULL` |
| `anagrafica_da_verificare` | `TRUE` |
| `creato_il` | preservare `PersonaCorso.creato_il` quando disponibile; altrimenti timestamp dell'apply |
| `aggiornato_il` | timestamp dell'apply che ha creato o modificato il target; un no-op non lo aggiorna |

`nome` e `cognome` restano volutamente nulli per **tutti** i record attivi importati. Non vengono introdotte euristiche basate su spazi, numero di parole, titoli, apostrofi o trattini.

Il nome completo legacy serve esclusivamente come dato transitorio per la successiva verifica manuale.

### 16.2 Codice fiscale

A2 riusa esattamente la normalizzazione di A1.

Non viene introdotta in A2 una nuova validazione formale del codice fiscale.

Se il valore non può essere memorizzato secondo i limiti A1:

- `Persona.codice_fiscale` resta `NULL`;
- il record viene creato comunque;
- il report contiene un warning `INVALID_TAX_CODE`;
- il valore originale non compare nel report.

CF coincidenti tra persone diverse non bloccano A2 e non provocano fusioni.

---

## 17. PAZ-A2.3 — record legacy già anonimizzati

Un `PersonaCorso` con `dati_anonimizzati_il IS NOT NULL` viene mappato, ma **non deve ricreare alcun dato identificativo**.

Proiezione:

| Campo `Persona` | Regola |
|---|---|
| `legacy_persona_corso_id` | ID legacy |
| `legacy_nome_completo` | `NULL` |
| `nome` / `cognome` | `NULL` |
| `codice_fiscale` | `NULL` |
| altri dati anagrafici | `NULL` |
| `stato` | `archiviata` |
| `archiviato_il` | `PersonaCorso.dati_anonimizzati_il` |
| `anagrafica_da_verificare` | `FALSE` |
| recapiti | nessuno |

La riga v2 è quindi un **placeholder tecnico di mapping**, non una nuova anagrafica utilizzabile.

### 17.1 Blocker privacy

Se `dati_anonimizzati_il` è valorizzato ma il legacy contiene ancora identificativi incompatibili con la procedura di anonimizzazione corrente, il dry-run emette:

`ANONYMIZED_SOURCE_HAS_RESIDUAL_PII`

e l'apply è vietato.

Sono considerati segnali bloccanti almeno:

- telefono non vuoto;
- email non vuota;
- codice fiscale non vuoto;
- note non vuote;
- `nome_bambino` o `eta_bambino` non vuoti;
- nome diverso dal placeholder previsto dalla procedura legacy.

A2 non tenta di “correggere” il legacy e non copia tali dati.

Il placeholder deve provenire dalla stessa costante usata dalla procedura legacy, attualmente `[dati anonimizzati]`, per evitare due definizioni divergenti. Se il timestamp è nullo ma il nome coincide con quel placeholder, il record è in uno stato privacy ambiguo: il dry-run emette `ANONYMIZATION_STATE_INCONSISTENT` e blocca l'apply. Anche un timestamp di anonimizzazione non valido o nel futuro è bloccante.

### 17.2 Anonimizzazione avvenuta dopo un primo backfill

Se un record precedentemente attivo viene anonimizzato nel legacy prima del cutover, un successivo piano A2 deve:

1. passare la `Persona` a `archiviata`;
2. valorizzare `archiviato_il`;
3. azzerare `legacy_nome_completo` e `codice_fiscale`;
4. lasciare `nome`, `cognome` e gli altri campi anagrafici nulli;
5. eliminare fisicamente tutti i recapiti v2 della persona, perché la sola archiviazione conserverebbe telefono/email e contraddirebbe l'anonimizzazione;
6. non creare alcuna nuova informazione identificativa.

Una inversione dell'anonimizzazione legacy viene considerata anomala e richiede revisione manuale.

L'eliminazione dei recapiti in questo caso è un'eccezione privacy esplicita al normale percorso di archiviazione previsto da A1. Non è un hard delete amministrativo ordinario: avviene soltanto durante la propagazione verificata di una cancellazione già eseguita nel legacy. Il report conserva esclusivamente il numero di righe eliminate, mai i valori.

---

## 18. PAZ-A2.4 — recapiti

Per ogni `PersonaCorso` attivo:

### Telefono

Se `telefono` è valido secondo A1:

- creare/riconciliare un `RecapitoPersona`;
- `tipo = telefono`;
- `valore` conserva il valore destinato alla visualizzazione, ripulito solo ai margini;
- `valore_normalizzato` usa `normalize_phone_number`;
- `principale = TRUE`.

Se è presente ma non valido:

- non creare il recapito;
- emettere warning `INVALID_PHONE`;
- non interrompere da solo il backfill.

### Email

Stessa regola:

- `tipo = email`;
- normalizzazione tramite `normalize_email_address`;
- `principale = TRUE`;
- input non valido → `INVALID_EMAIL`, senza copia del valore.

### 18.1 Nessuna deduplicazione tra persone

Lo stesso telefono/email può restare associato a più `Persona`, perché A2 deve rappresentare fedelmente il legacy, non decidere che due righe siano la stessa persona.

Le collisioni vengono solo riportate per ID legacy.

### 18.2 Riconciliazione su rerun

Finché la v2 non è aperta a modifiche manuali, A2 è proprietaria dei recapiti delle persone con `legacy_persona_corso_id`.

Se il valore legacy cambia:

- il precedente recapito attivo viene archiviato e perde `principale`;
- il nuovo recapito valido diventa principale;
- se il nuovo valore coincide con un recapito già archiviato della stessa persona/tipo, riattivare quella riga invece di crearne una duplicata.

Se il valore viene rimosso o diventa invalido:

- l'eventuale recapito principale precedente viene archiviato;
- nessun recapito nuovo viene creato.

Questo rispetta il vincolo UNIQUE A1 e impedisce hard delete.

---

## 19. PAZ-A2.5 — dati legacy che A2 non copia

### `nome_bambino` / `eta_bambino`

Non producono:

- `Persona` minori;
- `RelazionePersona`;
- nome/età nel record adulto v2.

Il report registra soltanto il codice:

`LEGACY_CHILD_FIELDS_PRESENT`

e il conteggio interessato.

### `note`

`PersonaCorso.note` non viene copiata in A2.

Motivo: il nuovo dominio `NotaPaziente` non esiste ancora e il campo legacy può contenere informazioni eterogenee o sensibili.

Il report usa soltanto:

`LEGACY_NOTE_PRESENT`

senza testo.

### Consensi e pratiche

Restano esclusivamente legacy. Nessuna copia o nuova FK viene creata in A2.

---

## 20. PAZ-A2.6 — dry-run e piano applicabile

Il **dry-run è il comportamento predefinito**.

Comando proposto:

```bash
flask --app app patients backfill-identities \
  --dry-run \
  --plan-file /percorso/sicuro/paz-a2-plan.json
```

L'apply non può essere eseguito senza un piano generato da un dry-run:

```bash
flask --app app patients backfill-identities \
  --apply \
  --plan-file /percorso/sicuro/paz-a2-plan.json
```

### 20.1 Contenuto del piano

Il piano contiene solo metadati minimizzati:

- `plan_version`;
- `run_id`;
- `generated_at` ed `expires_at` in UTC;
- revisione del codice rilevata da Git o dall'identificativo di build configurato;
- revisione Alembic DB rilevata;
- fingerprint HMAC dell'ambiente/database, senza URL o credenziali in chiaro;
- numero sorgenti;
- ID legacy;
- timestamp di aggiornamento/anonimizzazione;
- azione prevista;
- codici warning/blocker;
- fingerprint HMAC della sorgente e dello stato target atteso;
- conteggi aggregati;
- `plan_signature` dell'intero documento.

Non contiene:

- nomi;
- CF;
- telefoni;
- email;
- note;
- nome/età bambino;
- valori normalizzati.

Il file deve essere scritto in modo atomico con permessi `0600`, senza seguire link simbolici. Un file esistente non viene sovrascritto salvo opzione esplicita; anche in quel caso si usa file temporaneo nella stessa directory e rename atomico.

Durante l'apply il file viene aperto una sola volta come file regolare, rifiutando link simbolici e permessi di gruppo/altri quando il sistema li espone; contenuto e metadati usati per la verifica provengono dallo stesso file descriptor. Questo evita sostituzioni tra controllo e lettura.

### 20.2 Integrità, firma e fingerprint del piano

I fingerprint per record dimostrano che sorgente e target non sono cambiati tra dry-run e apply. Non proteggono però da soli azioni, conteggi o metadati del piano: l'intero documento deve quindi essere firmato.

Fingerprint e firma non vengono memorizzati come dati anagrafici nel database.

Strategia proposta:

1. validare il piano con uno schema chiuso e versionato, rifiutando campi sconosciuti e tipi ambigui;
2. serializzare JSON UTF-8 in forma canonica, con chiavi ordinate, separatori compatti, timestamp UTC e ordinamento dei record per ID legacy;
3. derivare dalla `SECRET_KEY` una sottochiave con `HMAC-SHA256(secret_key, "PAZ-A2-plan-v1")`, senza usare la chiave web direttamente come firma del piano;
4. generare per ogni riga un fingerprint keyed dei campi sorgente rilevanti, inclusi valori originali, timestamp e stato di anonimizzazione;
5. generare un fingerprint keyed dello stato target A2 atteso, usando un marcatore esplicito quando il mapping non esiste;
6. calcolare un fingerprint keyed dell'ambiente a partire da `APP_ENV` e dall'identità canonica della connessione (dialetto, host, porta e database/percorso), escludendo username, password e parametri segreti e senza salvare quei valori in chiaro;
7. calcolare `plan_signature` sull'intero piano canonico escluso il solo campo firma;
8. confrontare ogni HMAC con `hmac.compare_digest` durante l'apply.

Questa scelta è diversa dal fingerprint rimosso da A1:

- qui il valore è temporaneo;
- è verificato end-to-end dall'applicazione;
- SQL diretto non può “certificare” un piano falso;
- non viene usato come vincolo persistente del database.

Il piano scade dopo una finestra breve e configurata, proposta iniziale 60 minuti. Firma errata, schema/versione sconosciuti o file alterato producono `INVALID_PLAN`; ambiente diverso produce `PLAN_ENVIRONMENT_MISMATCH`; sorgente cambiata produce `STALE_PLAN`; target cambiato produce `STALE_TARGET`; piano scaduto produce `EXPIRED_PLAN`.

La revisione del codice usa, in ordine, `APP_BUILD_REVISION`, l'eventuale identificativo commit esposto dall'hosting oppure Git locale. L'apply è vietato se la revisione non è determinabile o non coincide; non si assume che `.git` sia disponibile nel runtime.

Dry-run con produzione del piano e apply richiedono una `SECRET_KEY` stabile di almeno 32 caratteri. Se `SECRET_KEY_IS_EPHEMERAL` è vero, il comando si ferma con `UNSTABLE_PLAN_KEY`: due processi CLI distinti genererebbero altrimenti chiavi diverse e il piano non sarebbe verificabile. La chiave e la sottochiave non devono mai comparire in output, piano, report o log.

Un piano che prevedeva modifiche diventa naturalmente `STALE_TARGET` dopo un apply riuscito. Un piano che era già interamente no-op può essere rieseguito come no-op senza modificare timestamp o dati; l'idempotenza non richiede una nuova tabella di esecuzioni né una migration A2.

---

## 21. PAZ-A2.7 — precondizioni e ordine dell'apply

Prima di aprire la transazione il comando può verificare soltanto condizioni che non dipendono dallo stato mutevole del database:

1. schema e versione del file;
2. firma completa del piano;
3. scadenza;
4. revisione del codice;
5. assenza di blocker già presenti nel piano.

Il comando non deve lanciare `flask db check` come sottoprocesso. `db check` resta un gate operativo eseguito dall'operatore immediatamente prima di dry-run/apply; il comando verifica direttamente la revisione Alembic attesa e le precondizioni strutturali necessarie ad A2.

Dopo avere aperto la transazione e acquisito il lock A2, il comando rilegge e blocca lo stato necessario, quindi verifica:

1. A1 è realmente integrata e la revisione DB attesa è presente;
2. il piano appartiene all'ambiente/database corrente;
3. i fingerprint sorgente coincidono;
4. i fingerprint target coincidono;
5. non sono apparse o scomparse righe `PersonaCorso` rispetto al piano;
6. `Appuntamento.persona_id` è ancora sempre `NULL`;
7. `CallSonno.persona_id` è ancora sempre `NULL`;
8. `IscrizioneCorso.persona_v2_id` è ancora sempre `NULL`;
9. non esistono relazioni/fusioni/deduplicazioni v2 operative introdotte fuori fase;
10. non esistono `Persona` v2 non riconducibili alla proprietà prevista di A2, salvo eccezioni esplicitamente autorizzate e testate;
11. nessun target già mappato contiene dati fuori dal dominio posseduto da A2.

Le verifiche dipendenti dal DB e tutte le scritture devono condividere la stessa transazione e lo stesso lock. Non deve esistere una finestra tra il controllo dei fingerprint e la scrittura. Qualunque violazione P0/P1 causa rollback e blocca l'intera esecuzione.

---

## 22. PAZ-A2.8 — proprietà dei campi durante la migrazione

Fino all'inizio di A4 non esiste una UI autorizzata a modificare le identità v2.

A2 possiede soltanto:

- `legacy_persona_corso_id`;
- `legacy_nome_completo`;
- `codice_fiscale`;
- `stato`;
- `archiviato_il`;
- `anagrafica_da_verificare`;
- recapiti delle `Persona` mappate dal legacy;
- `creato_il` alla creazione iniziale e `aggiornato_il` soltanto quando A2 modifica realmente il target.

A2 non possiede e non valorizza:

- `nome`;
- `cognome`;
- data di nascita;
- sesso anagrafico;
- luogo di nascita;
- residenza;
- relazioni.

Se una `Persona` mappata presenta valori fuori dal dominio A2, il comando non li sovrascrive e produce:

`TARGET_OUT_OF_PHASE_CHANGE`

come blocker.

Questo impedisce che un rerun del backfill cancelli una eventuale modifica manuale non prevista.

---

## 23. PAZ-A2.9 — idempotenza e transazione

### Idempotenza

Una seconda esecuzione sullo stesso stato sorgente deve produrre:

- zero nuove `Persona`;
- zero nuovi recapiti;
- zero variazioni di dati;
- stesso mapping;
- report `already_synced`.

La prova principale usa un nuovo piano generato da un nuovo dry-run. Come indicato nella sezione 20.2, il riuso di un piano che aveva previsto scritture diventa stale per effetto del target cambiato; soltanto un piano già interamente no-op può restare un no-op.

Il vincolo UNIQUE su `legacy_persona_corso_id` resta l'ultima difesa DB contro duplicazioni.

### Delta

Se il legacy cambia prima di A3:

1. generare un nuovo dry-run;
2. produrre un nuovo piano;
3. riconciliare soltanto i record cambiati;
4. eseguire nuovamente il report di consistenza.

Nessuna pratica viene collegata durante il delta A2.

### Transazione di scrittura

L'apply utilizza una singola transazione per lock, rilettura, validazione, scritture target e audit di successo.

Se un errore di integrità o un blocker viene rilevato durante la scrittura:

- rollback completo;
- nessun target parziale viene considerato valido;
- il report registra soltanto run ID, fase, codice errore e conteggi minimizzati.

### Esecuzioni concorrenti

Non devono esistere due A2 apply contemporanei.

Requisito proposto:

- PostgreSQL: acquisire con `pg_try_advisory_xact_lock` un lock advisory transaction-scoped dedicato ad A2, poi bloccare `persona_corso` contro INSERT/UPDATE/DELETE per tutta la rilettura e l'apply; eventuali target esistenti vengono letti con lock;
- SQLite/test locale: aprire la connessione di apply con timeout di attesa nullo o minimo e acquisire `BEGIN IMMEDIATE` **prima di qualunque query che avvii implicitamente una transazione**, poi ripetere tutte le verifiche e scrivere sulla stessa connessione/sessione.

Il secondo writer deve fallire rapidamente con un errore operativo chiaro, non attendere e applicare un secondo backfill indistinguibile.

Le istruzioni DB-specifiche sono isolate in due piccoli adapter di lock e coperte da test reali. Il dry-run resta read-only e non acquisisce un lock di scrittura; legge le sorgenti in ordine stabile e produce comunque un piano che l'apply deve rivalidare integralmente.

---

## 24. PAZ-A2.10 — collisioni e anomalie

A2 può diagnosticare ma non risolvere.

### Warning non bloccanti

- `INVALID_PHONE`;
- `INVALID_EMAIL`;
- `INVALID_TAX_CODE`;
- `LEGACY_CHILD_FIELDS_PRESENT`;
- `LEGACY_NOTE_PRESENT`;
- `DUPLICATE_NORMALIZED_TAX_CODE`;
- `DUPLICATE_NORMALIZED_PHONE`;
- `DUPLICATE_NORMALIZED_EMAIL`;
- `MISSING_LEGACY_NAME`.

Le collisioni indicano esclusivamente gruppi di **ID legacy**, mai i valori che hanno colliso.

### Blocker

Almeno:

- `A1_NOT_READY`;
- `INVALID_PLAN`;
- `EXPIRED_PLAN`;
- `STALE_PLAN`;
- `STALE_TARGET`;
- `PLAN_ENVIRONMENT_MISMATCH`;
- `CODE_REVISION_UNKNOWN`;
- `CODE_REVISION_MISMATCH`;
- `UNSTABLE_PLAN_KEY`;
- `ANONYMIZED_SOURCE_HAS_RESIDUAL_PII`;
- `ANONYMIZATION_STATE_INCONSISTENT`;
- `INVALID_ANONYMIZATION_TIMESTAMP`;
- `ANONYMIZATION_REVERSED`;
- `TARGET_OUT_OF_PHASE_CHANGE`;
- `PRACTICE_V2_FK_ALREADY_POPULATED`;
- `UNEXPECTED_V2_DOMAIN_DATA`;
- `CONCURRENT_A2_APPLY`;
- errore di integrità DB non previsto.

Gli errori di validazione di un singolo recapito non sono blocker, perché il dato legacy resta disponibile e il record può essere corretto successivamente.

---

## 25. PAZ-A2.11 — report e privacy

### Output console

Solo:

- run ID;
- modalità dry-run/apply;
- numero sorgenti;
- create/update/no-op;
- recapiti creati/archiviati/riattivati;
- persone attive/placeholder archiviate;
- numero warning per codice;
- numero blocker per codice;
- esito.

### Report JSON

Può contenere:

- ID tecnici;
- codici evento;
- timestamp;
- conteggi;
- fingerprint keyed;
- revisione Git/Alembic;
- stato dell'esecuzione.

Non può contenere dati identificativi o sanitari.

Piano e report restano comunque artefatti pseudonimi riservati: non vanno committati, caricati nella documentazione, esposti via HTTP o inclusi nei backup ordinari. Il piano viene eliminato dopo l'apply riuscito; in caso di errore viene conservato soltanto per il tempo strettamente necessario alla diagnosi, con limite operativo iniziale di 24 ore. Il report segue la retention operativa approvata e contiene solo i campi ammessi sopra.

### Audit DB

Dopo un apply riuscito può essere registrato **un solo evento operativo riassuntivo** in `RegistroEvento`, con:

- `run_id`;
- versione piano;
- conteggi;
- `plan_digest`, calcolato come SHA-256 della `plan_signature` e non dal contenuto PII sorgente;
- esito.

Nessun `RegistroModifica` per singola persona è necessario in A2: il mapping è già dimostrato da `legacy_persona_corso_id` e dal piano/report.

L'evento di successo viene aggiunto tramite la stessa sessione dell'apply e viene committato atomicamente con il backfill. Non deve essere usata dentro la transazione la funzione corrente `registra_evento`, perché effettua autonomamente `commit` e gestisce gli errori separatamente: A2 deve costruire il record senza commit intermedio.

Un apply fallito può registrare un evento di errore soltanto **dopo** il rollback, in una nuova transazione, sempre senza PII. Il fallimento dell'audit di errore non deve mascherare l'eccezione originale e deve restare osservabile nei log minimizzati.

---

## 26. PAZ-A2.12 — matrice minima dei test

### Trasformazione

- record legacy completo;
- nome Unicode;
- nome vuoto/anomalo;
- CF normalizzabile;
- CF non memorizzabile;
- telefono nazionale;
- telefono internazionale `+`;
- telefono internazionale `00`;
- telefono invalido;
- email valida/invalida;
- record senza recapiti;
- record con note;
- record con `nome_bambino`/`eta_bambino`.

### Anonimizzazione

- sorgente già anonimizzata → placeholder archiviato senza PII;
- sorgente anonimizzata con residui PII → blocker;
- placeholder legacy senza timestamp o timestamp futuro/non valido → blocker;
- sorgente attiva migrata e poi anonimizzata → PII v2 rimossa e recapiti eliminati fisicamente;
- tentata inversione anonimizzazione → blocker.

### Dry-run/piano

- zero scritture DB;
- report privo dei valori PII usati nel fixture;
- piano completo firmato correttamente e confronto constant-time;
- modifica di azione, ID, conteggio, scadenza o warning nel file → `INVALID_PLAN`;
- campo sconosciuto o tipo ambiguo → `INVALID_PLAN`;
- piano scaduto → `EXPIRED_PLAN`;
- modifica del sorgente dopo il dry-run → `STALE_PLAN`;
- modifica del target dopo il dry-run → `STALE_TARGET`;
- aggiunta/rimozione sorgente → `STALE_PLAN`;
- piano generato per altro database con la stessa chiave → rifiutato;
- revisione codice assente o diversa → rifiutata;
- chiave differente → rifiutato.
- chiave effimera o troppo corta → `UNSTABLE_PLAN_KEY`, senza generare un piano applicabile.

### Idempotenza

- primo apply crea mapping;
- nuovo dry-run e secondo apply identico sono no-op;
- riuso di un piano che prevedeva scritture → `STALE_TARGET`;
- riuso di un piano interamente no-op → ancora no-op, senza aggiornare timestamp;
- nessuna duplicazione `Persona`;
- nessuna duplicazione recapiti;
- cambio telefono/email → archiviazione + nuovo principale;
- ritorno a un recapito storico → riattivazione;
- rimozione recapito → archiviazione.

### Collisioni

- stesso CF su due legacy → due `Persona`, warning;
- stesso telefono → due `Persona`, warning;
- stessa email → due `Persona`, warning;
- nessuna `SegnalazioneDuplicato` creata.

### Confini di fase

- nessuna `RelazionePersona`;
- nessuna `FusionePersona`;
- nessuna nuova segnalazione duplicato persistita;
- `Appuntamento.persona_id` sempre NULL;
- `CallSonno.persona_id` sempre NULL;
- `IscrizioneCorso.persona_v2_id` sempre NULL;
- `PersonaCorso` invariata byte/logicamente nei campi di business;
- `note` non copiate;
- minori non creati.

### Drift target

- target con `nome`/`cognome` manuali → blocker;
- target con dati anagrafici fuori A2 → blocker;
- target conforme già sincronizzato → no-op.

### Transazioni e concorrenza

- errore sul record N → rollback di tutte le scritture del piano;
- verifica che nessun commit intermedio avvenga durante audit o scrittura;
- evento di successo atomico con il backfill;
- evento di errore scritto solo dopo rollback;
- due apply concorrenti PostgreSQL → uno solo acquisisce il lock;
- modifica o inserimento concorrente in `PersonaCorso` durante apply PostgreSQL → bloccato fino a fine transazione;
- test equivalente locale/SQLite con `BEGIN IMMEDIATE` acquisito prima dell'autobegin ORM;
- rerun dopo rollback → successo e mapping unico.

### Cross-database e regressione

- SQLite;
- PostgreSQL reale;
- `flask --app app db check` resta verde;
- suite applicativa completa;
- `git diff --check`;
- verifica che A2 non richieda una nuova migration Alembic.

I test privacy devono usare valori sentinella univoci e verificare che non compaiano in piano, report, output console, eccezioni, log o `RegistroEvento`. I test dei file devono coprire permessi `0600`, mancato overwrite predefinito, link simbolici rifiutati e rename atomico.

---

## 27. Criteri di accettazione PAZ-A2

PAZ-A2 può essere definita `Implementata localmente` soltanto se:

1. PAZ-A1 è stata integrata e verificata nel checkout reale;
2. A2 è stata approvata esplicitamente per lo sviluppo;
3. il comando è dry-run per default;
4. l'apply richiede esplicitamente un piano valido;
5. piano e report non contengono PII in chiaro e il file viene scritto atomicamente con permessi restrittivi;
6. schema, firma completa, scadenza, revisione codice e identità ambiente/database del piano sono verificati usando una chiave stabile e adeguata;
7. il dry-run contabilizza esattamente una volta ogni `PersonaCorso`; l'apply parte soltanto se nessun blocker è presente;
8. nessun nome/cognome è inferito automaticamente;
9. nessun minore o relazione viene creato;
10. nessuna nota legacy viene copiata;
11. record anonimizzati non ricreano PII e i recapiti v2 eventualmente esistenti vengono eliminati;
12. recapiti invalidi sono omessi e segnalati senza perdita del legacy;
13. collisioni tra persone non causano deduplicazione;
14. il rerun tramite nuovo piano è idempotente; un piano che prevedeva scritture diventa stale, mentre un piano già no-op resta no-op;
15. un cambio del sorgente o del target invalida il piano precedente;
16. rilettura, lock, verifiche DB, scritture e audit di successo condividono una sola transazione;
17. errori di scrittura producono rollback completo senza commit intermedi;
18. due apply concorrenti non possono procedere insieme e le sorgenti non possono cambiare durante l'apply;
19. tutte le FK pratica v2 restano NULL;
20. il legacy resta fonte di verità e non viene modificato;
21. SQLite e PostgreSQL reale superano i test A2;
22. la suite applicativa completa non mostra regressioni;
23. `db check` resta verde;
24. il diff è revisionato manualmente;
25. nessun dato reale o database esterno è usato senza autorizzazione separata.

---

## 28. Uscita prevista da A2

Dopo un A2 verificato devono esistere:

- mapping 1:1 `PersonaCorso → Persona`;
- recapiti v2 coerenti con il legacy valido;
- placeholder archiviati per sorgenti già anonimizzate;
- elenco minimizzato delle anagrafiche da verificare;
- report delle collisioni senza fusioni;
- zero collegamenti delle pratiche alle nuove FK.

Soltanto a quel punto può essere progettata/implementata **PAZ-A3 — collegamento controllato delle pratiche**.

A3 dovrà utilizzare esclusivamente il mapping `legacy_persona_corso_id`, mai somiglianze di nome, telefono o email.

---

## 29. Esito della revisione progettuale A2

La proposta revisionata è coerente con il perimetro A1 e non presenta P0/P1 progettuali noti. In particolare:

- nessun dato di pratica, consenso, minore o relazione entra in A2;
- il piano è autenticato integralmente, legato a codice, ambiente, database, sorgente e target e ha scadenza breve;
- la rilettura che precede le scritture avviene sotto lo stesso lock e nella stessa transazione dell'apply;
- una anonimizzazione legacy rimuove realmente i recapiti v2 invece di conservarne i valori archiviati;
- audit e backfill di successo sono atomici e non usano helper che effettuano commit autonomi;
- idempotenza e concorrenza hanno semantica esplicita su SQLite e PostgreSQL.

Restano gate di processo, non difetti risolti da questo documento:

1. nel checkout verificato `ebab09b`, PAZ-A1 non è ancora integrata;
2. A2 resta una proposta e richiede approvazione esplicita prima dello sviluppo;
3. nessuna garanzia runtime A2 può essere dichiarata prima dell'implementazione e dell'esecuzione dell'intera matrice della sezione 26 su database sintetici.

---

## 30. Candidata di implementazione PAZ-A2 v1 — pacchetto per code review

> **Stato:** `In revisione`.
>
> Questa sezione descrive il codice candidato prodotto sulla copia isolata dello ZIP originale con **PAZ-A1 v4 applicata come baseline di revisione**. Non dimostra che A1 o A2 siano integrate nel repository reale, committate o deployate.
>
> La specifica A2 di riferimento è il documento revisionato con SHA-256 `4a6b71c4937df265cc93c06ac48a6539bda15e367550742be36d97bf3fc0efcf`.

### 30.1 Perimetro implementato

La candidata implementa l'intero perimetro software di PAZ-A2 definito nelle sezioni 14–29:

- servizio applicativo separato dal web;
- dry-run firmato e read-only;
- apply da piano esistente;
- piano legato a code revision, environment, database/schema, source e target;
- TTL e chiave stabile obbligatoria;
- file plan privato e atomico;
- mapping 1:1 `PersonaCorso → Persona`;
- recapiti idempotenti e storicizzati;
- propagazione privacy con cancellazione fisica dei recapiti v2;
- collisioni diagnostiche senza deduplicazione;
- lock SQLite/PostgreSQL;
- rilettura, validazione, scrittura e audit nella stessa transazione;
- audit di successo senza usare `registra_evento()`;
- report minimizzato;
- suite SQLite e suite PostgreSQL opt-in.

Non vengono implementati A3, A4 o A5. Le specifiche disponibili definiscono per tali fasi soltanto il perimetro generale, non abbastanza dettagli per introdurre in sicurezza collegamenti pratiche, UI/cutover o cleanup. Non vengono quindi inventate decisioni mancanti.

### 30.2 File nuovi

#### `patient_backfill.py`

Responsabilità:

- `BackfillModels`: registry esplicito dei modelli ricevuti dall'app;
- validazione chiusa dello schema piano;
- JSON canonico;
- derivazione della sottochiave A2;
- firma HMAC dell'intero piano;
- fingerprint keyed source/target;
- risoluzione code revision;
- fingerprint ambiente/database, incluso `current_schema()` PostgreSQL;
- lettura revisione Alembic;
- assessment privacy legacy;
- collision analysis;
- dry-run planner;
- lettura/scrittura sicura dei file;
- lock adapter PostgreSQL/SQLite;
- riconciliazione Persona/RecapitoPersona;
- hard-delete recapiti esclusivamente nel percorso privacy;
- apply transazionale;
- audit atomico;
- report minimizzato.

Il modulo non importa Flask e non accede al `db.session` globale.

#### `tests/test_patient_a2_backfill.py`

Suite SQLAlchemy/SQLite sintetica per:

- canonicalizzazione/firma;
- chiave stabile;
- fingerprint database senza credenziali;
- privacy state legacy;
- dry-run senza scritture;
- assenza PII nel piano/report/audit;
- schema chiuso;
- rifiuto `bool` come ID;
- permessi file e symlink;
- apply mapping/recapiti/audit;
- stale source/target;
- TTL;
- idempotenza e riuso piano no-op;
- collisioni senza deduplica;
- recapito invalido/archiviazione;
- riattivazione recapito storico;
- anonimizzazione con cancellazione recapiti;
- inversione anonimizzazione;
- target fuori fase;
- FK pratica già valorizzata;
- rollback completo;
- contesa SQLite.

#### `tests/test_patient_a2_postgres.py`

Suite opt-in con `PAZ_A2_POSTGRES_URL`:

- schema PostgreSQL isolato;
- esecuzione della catena Alembic reale fino ad A1 tramite Flask-Migrate;
- `flask db check` prima e dopo A2;
- dry-run/apply reale;
- advisory lock transaction-scoped;
- secondo apply respinto;
- `persona_corso` bloccata contro scritture concorrenti durante l'apply;
- cleanup dello schema usa-e-getta.

### 30.3 File modificati

#### `patient_data.py`

Aggiunta una singola costante condivisa:

`ANONYMIZED_PERSON_PLACEHOLDER = "[dati anonimizzati]"`

Lo scopo è evitare una seconda definizione divergente tra la procedura privacy legacy e A2.

#### `app.py`

Modifiche:

- usa la costante condivisa nella procedura privacy esistente;
- importa il servizio A2;
- aggiunge `SASession` per il planner dry-run separato;
- registra il gruppo CLI `patients`;
- registra `patients backfill-identities`;
- costruisce esplicitamente `BackfillModels`;
- nessuna route/template/UI usa A2;
- nessuna FK pratica viene popolata dai flussi esistenti.

CLI candidata:

```bash
flask --app app patients backfill-identities \
  --plan-file /percorso/privato/paz-a2-plan.json
```

Il dry-run è il default. L'apply è esplicito:

```bash
flask --app app patients backfill-identities \
  --apply \
  --plan-file /percorso/privato/paz-a2-plan.json
```

Opzioni addizionali candidate:

- `--overwrite-plan` solo dry-run;
- `--report-file` opzionale;
- `--overwrite-report` per sostituzione atomica del report.

Queste opzioni non consentono di bypassare firma, TTL, blocker, revision mismatch o lock.

#### `config.py`

Aggiunte:

- `APP_BUILD_REVISION`, con fallback a `RENDER_GIT_COMMIT`;
- `PAZ_A2_PLAN_TTL_SECONDS`, default 3600.

#### `.env.example` e `README.md`

Documentate le variabili operative A2:

- `APP_BUILD_REVISION`;
- `PAZ_A2_PLAN_TTL_SECONDS` (default 3600).

Non vengono aggiunti segreti o valori reali.

#### `.gitignore`

Aggiunti pattern difensivi:

- `paz-a2-plan*.json`;
- `paz-a2-report*.json`.

Gli artefatti restano comunque da generare preferibilmente fuori dal repository o sotto `instance/`.

#### `README.md`

Documentate le due nuove variabili operative senza segreti o valori reali.

### 30.4 Dettagli implementativi proposti alla revisione

#### `global_blockers`

Il piano contiene una lista top-level `global_blockers` firmata. Serve per condizioni non attribuibili a un singolo `PersonaCorso`, come:

- FK pratica v2 già popolate;
- dati v2 fuori fase.

#### `collisions`

Il piano/report contiene gruppi minimizzati:

```json
{"code": "DUPLICATE_NORMALIZED_PHONE", "legacy_ids": [12, 18]}
```

Non contiene il valore che ha colliso. Questo rende concretamente utilizzabile il requisito della sezione 24 secondo cui le collisioni devono indicare soltanto ID legacy.

#### PostgreSQL target locking

Oltre all'advisory lock A2, la candidata usa table lock per eliminare race con writer non-A2 durante la finestra di manutenzione:

- `persona_corso` in `SHARE MODE`;
- `persona` e `recapito_persona` in `SHARE ROW EXCLUSIVE MODE`;
- tabelle dei confini A1/A2 in `SHARE MODE`.

Questa scelta è intenzionalmente conservativa e va revisionata rispetto ai tempi attesi del backfill. SQLite usa `BEGIN IMMEDIATE`, che serializza il writer sull'intero database.

#### Environment fingerprint PostgreSQL

Oltre a dialetto/host/porta/database, il fingerprint include `current_schema()` letto sulla **stessa connessione/sessione** usata dal planner/apply. Questo impedisce il riuso accidentale di un piano tra due schemi isolati dello stesso database.

### 30.5 Privacy e dati non persistiti

Il codice candidato non inserisce in piano/report/audit:

- nome;
- CF;
- telefono;
- email;
- note;
- nome/età bambino;
- valori normalizzati.

I fingerprint usano tali valori esclusivamente in memoria e persistono soltanto HMAC keyed.

Il percorso di anonimizzazione A2 elimina fisicamente i `RecapitoPersona` della persona, come eccezione privacy esplicita. Nessuna route ordinaria espone questa funzione.

### 30.6 Transazione e audit

Apply PostgreSQL/SQLite:

1. acquisizione lock;
2. revisione Alembic;
3. environment/database fingerprint;
4. rilettura source;
5. rilettura target;
6. verifica fingerprint/action/warning/blocker;
7. verifica confini A2;
8. riconciliazione target;
9. flush;
10. audit successo aggiunto alla stessa sessione;
11. commit unico.

In errore:

- rollback completo;
- audit errore in nuova transazione best-effort;
- nessun helper con commit autonomo dentro l'apply.

### 30.7 Evidenze ottenute in questo ambiente

Comandi effettivamente eseguiti sulla copia isolata:

```text
python -m py_compile patient_backfill.py patient_data.py config.py app.py
```

Esito: **OK**.

Suite autonome A1+A2 eseguibili senza Flask:

```text
pytest -q \
  tests/test_patient_data.py \
  tests/test_patient_a1_schema.py \
  tests/test_patient_a2_backfill.py \
  tests/test_patient_a2_postgres.py
```

Esito corrente:

```text
72 passed, 3 skipped
```

I 3 skip sono esclusivamente i test PostgreSQL A2 perché `PAZ_A2_POSTGRES_URL` non è configurata nel runtime di questa revisione.

Suite A2 SQLite:

```text
30 passed
```

Controllo diff sulla tranche A2 rispetto alla baseline A1 v4:

```text
git diff --check
```

Esito: **OK**.

### 30.8 Verifiche non dichiarate come superate

In questo runtime non sono disponibili Flask/Flask-SQLAlchemy/Flask-Migrate/psycopg, quindi non sono state eseguite qui:

- suite `tests/test_app.py` completa;
- suite `tests/test_migrations.py` tramite `flask db`;
- `flask --app app db check` sulla candidata A2;
- i 3 test A2 PostgreSQL reali.

Il tentativo di eseguire `tests/test_migrations.py` produce fallimenti di bootstrap con `No module named flask`; non è stato classificato come regressione del codice.

Questi controlli sono gate obbligatori della code review nel checkout/virtualenv reale.

### 30.9 Stato rispetto ad A3–A5

La richiesta di produrre "tutto il codice rimasto" viene limitata al perimetro per cui esiste una specifica revisionata sufficiente.

- **A2:** codice candidato completo prodotto.
- **A3:** non implementato; le fonti definiscono soltanto mapping per ID legacy, confronto pratiche e stop su ambiguità, ma non ancora transazioni, conflitti, audit, delta e rollback in dettaglio.
- **A4:** non implementato; manca la specifica revisionata di UI, permessi, dual-read/write e cutover.
- **A5:** non implementato; cleanup distruttivo richiede finestra di stabilizzazione, backup/restore e approvazione separata.

Implementare A3–A5 ora richiederebbe introdurre decisioni non supportate dalla specifica corrente e contraddirebbe le regole di handoff delle sezioni 12, 13 e 29.

### 30.10 Prossima azione per il revisore

1. applicare A1 v4 su una copia del checkout reale aggiornato;
2. applicare sopra la patch A2 candidata;
3. verificare HEAD Git e head Alembic;
4. configurare un PostgreSQL di test usa-e-getta;
5. eseguire suite completa + `db check` + test A2 PostgreSQL;
6. revisionare in particolare:
   - lock PostgreSQL e durata;
   - schema piano `global_blockers`/`collisions`;
   - sicurezza filesystem;
   - ownership target A2;
   - atomicità audit;
   - anonimizzazione con hard delete recapiti;
   - CLI post-commit e gestione artefatti.

Nessun apply su dati reali è autorizzato da questa candidata.

---

## 31. Revisione indipendente della candidata A2 — 7 settembre 2026

### 31.1 Esito e perimetro della review

La patch A2 è stata applicata senza conflitti sopra la baseline A1 v4 indicata dal documento (`ebab09b` + A1 v4) in una copia isolata. La cartella sorgente allegata e il risultato della patch coincidono, esclusi i metadati Git e le cache locali.

Il nucleo progettuale è presente: dry-run predefinito, piano con schema chiuso e firma completa, binding a revisione/Alembic/ambiente/database/schema, TTL, rivalidazione nella transazione di apply, lock SQLite/PostgreSQL, hard delete dei recapiti limitato alla propagazione privacy e audit di successo atomico.

La candidata **non è però ancora accettabile né pronta per dati reali**. Restano un P0 privacy, più P1 funzionali e di verifica, e alcuni P2. Questa sezione aggiorna e prevale sulle conclusioni e sui gate ancora aperti delle sezioni 30.7–30.10; non modifica lo stato approvativo di A1/A2 e non autorizza deploy o apply.

### 31.2 P0 — sanitizzare tutte le eccezioni dell'apply

**Problema.** In `patient_backfill.py`, `apply_backfill_plan()` rilancia invariata ogni eccezione inattesa dopo il rollback e l'audit best-effort. In `app.py` la CLI converte in `ClickException` soltanto `PatientBackfillError` e `OSError`. Un `IntegrityError` SQLAlchemy può includere statement e parametri: nome, codice fiscale, telefono o email potrebbero quindi comparire nel traceback, in stderr o nei log. Questo viola il requisito della sezione 26 che vieta PII anche in eccezioni e log.

**Modifiche richieste.**

1. Dopo il rollback, tradurre gli errori DB e gli errori inattesi in un'eccezione applicativa sanitizzata con solo un codice stabile (`UNEXPECTED_INTEGRITY_ERROR` o `PATIENT_BACKFILL_ERROR`).
2. Non includere `str(exc)`, statement SQL, parametri, `repr(exc)` o chaining visibile dell'eccezione originale nell'output CLI.
3. Conservare la causa originale solo per diagnostica interna se è possibile impedirne in modo verificabile la serializzazione; in alternativa sopprimere esplicitamente il contesto quando l'errore attraversa la CLI.
4. Aggiungere test con sentinelle univoche che forzino un `IntegrityError` contenente PII e verifichino assenza delle sentinelle da eccezione esposta, stdout, stderr, log, report e `RegistroEvento`.

Questo P0 deve essere chiuso prima di qualunque prova con dati reali.

### 31.3 P1 — correzioni funzionali e operative

#### P1.1 — un `already_synced` può scrivere dati

`_contact_state_matches()` confronta il recapito principale soltanto per tipo e valore normalizzato. `_reconcile_contact()` riscrive invece sempre il valore visualizzato e può archiviare recapiti attivi non principali. Un cambio di sola formattazione, per esempio tra due rappresentazioni dello stesso numero normalizzato, può quindi essere pianificato e riportato come `already_synced` ma modificare il database senza aggiornare `Persona.aggiornato_il`.

**Modifica richiesta:** rendere il confronto di stato identico alle proprietà possedute dalla riconciliazione, includendo valore visualizzato, flag `principale`, `archiviato_il`, `etichetta` e presenza di ulteriori recapiti attivi; in alternativa impedire qualunque assegnazione quando l'azione è `already_synced`. Se esiste una differenza posseduta da A2, l'azione deve essere `update` e il timestamp deve rifletterla. Aggiungere test per formattazione display e recapito attivo non principale.

#### P1.2 — un nome legacy anomalo può interrompere il dry-run

All'inizio di `analyze_legacy_source()` il nome viene passato direttamente a `normalize_patient_name()` per riconoscere il placeholder, prima dell'uso di `_safe_normalize_name()`. Un nome oltre 100 caratteri solleva `PatientDataValidationError` e interrompe il comando invece di produrre `MISSING_LEGACY_NAME` o un codice anomalia minimizzato.

**Modifica richiesta:** riconoscere il placeholder con una funzione che non sollevi oppure riusare una sola normalizzazione sicura per entrambe le decisioni. Coprire almeno nome troppo lungo, tipo inatteso e sorgente anonimizzata con nome non valido, senza PII nell'errore.

#### P1.3 — il test PostgreSQL opt-in usa la configurazione SQLite

`tests/test_patient_a2_postgres.py::_run_flask_db()` imposta `FLASK_ENV=testing`, ma `TestingConfig` forza `SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'` e ignora `DATABASE_URL`. Di conseguenza `flask db upgrade/check` parte con `SQLiteImpl`; `db check` fallisce con `Target database is not up to date` e i tre test A2 PostgreSQL terminano in setup senza provare apply o lock.

**Modifica richiesta:** predisporre una configurazione test PostgreSQL esplicita oppure fare in modo che `TestingConfig` utilizzi un `DATABASE_URL` esplicitamente fornito per questo gate, mantenendo SQLite in-memory come default. Il test deve asserire `db.engine.dialect.name == 'postgresql'` e `current_schema()` uguale allo schema casuale prima dell'upgrade/apply, così non può produrre un falso positivo cross-database.

#### P1.4 — piano e report possono indicare lo stesso file

La CLI non impedisce che `--plan-file` e `--report-file` risolvano allo stesso percorso. Nel dry-run `--overwrite-report` può sostituire il piano con il report; nell'apply il report può essere scritto sul piano e subito eliminato dalla pulizia post-commit.

**Modifica richiesta:** risolvere e confrontare i due percorsi prima di leggere o scrivere, rifiutando equivalenza e alias tramite link ove rilevabile. Aggiungere test CLI sia per dry-run sia per apply, con e senza flag di overwrite, verificando che nessun artefatto venga perso.

#### P1.5 — manca il report strutturato dell'apply fallito

Il report viene costruito soltanto dopo un apply riuscito. In caso di blocker o errore durante la scrittura la CLI restituisce un messaggio/traceback, ma non produce il report minimizzato richiesto dalla sezione 23: run ID, fase, codice errore e conteggi ammessi.

**Modifica richiesta:** definire un risultato di fallimento sanitizzato dopo il rollback, renderlo disponibile alla CLI e scriverlo su `--report-file` senza mascherare l'errore originale sanitizzato. Non generare un report applicativo prima che il rollback sia terminato.

#### P1.6 — il fallimento dell'audit secondario non è osservabile

Il blocco `except Exception: pass` che protegge l'audit di errore rispetta la precedenza dell'errore originale, ma perde ogni evidenza che anche l'audit sia fallito, in contrasto con la sezione 25.

**Modifica richiesta:** emettere un log minimizzato con `run_id`, codice dell'errore applicativo e sola classe/codice del fallimento di audit. Non registrare messaggio DB, statement, parametri o altri valori potenzialmente identificativi.

### 31.4 P2 — robustezza, completezza del contratto e manutenibilità

1. **Output incompleto.** `ApplyResult.report()` non espone `source_count`, `active_sources` e `anonymized_sources`, sebbene l'output console definito nella sezione 25 li richieda. Aggiungerli al risultato sia dry-run sia apply e verificarli con test CLI.
2. **Writer/reader del piano non simmetrici.** Il reader rifiuta file oltre `MAX_PLAN_FILE_BYTES`, mentre il writer può produrli con successo. Verificare la dimensione prima del rename atomico e aggiungere i casi limite `MAX` e `MAX+1`.
3. **Copertura troppo isolata.** I test A2 SQLite ridefiniscono modelli SQLAlchemy ridotti e non invocano la CLI Flask. Aggiungere almeno un test con i modelli applicativi reali e `app.test_cli_runner()`, comprendendo gestione di piano/report, cancellazione del piano dopo successo e comportamento post-commit.
4. **Matrice test incompleta.** Aggiungere inserimento e rimozione di sorgenti dopo il piano, timestamp di anonimizzazione futuro, rerun dopo rollback, piano/report con stesso path, errori filesystem post-commit e sentinelle PII in ogni canale previsto dalla sezione 26.
5. **Modulo troppo esteso.** `patient_backfill.py` concentra schema/firma, sicurezza filesystem, identità ambiente, lock DB, trasformazione, audit e reporting in circa 1.600 righe. Dopo i fix funzionali, separare almeno gestione degli artefatti e adapter DB, senza introdurre nuove astrazioni di dominio o scope A3.

### 31.5 Evidenze ripetute durante questa review

Eseguite esclusivamente su copie e database sintetici usa-e-getta:

```text
patch A2 sopra A1 v4                         OK, nessun conflitto
git diff --check                             OK
suite A1+A2 autonoma                         72 passed, 3 skipped
suite completa                               356 passed, 6 skipped
SQLite flask db upgrade + db check           OK, nessun drift
test PostgreSQL A1 reale                     3 passed
test PostgreSQL A2 opt-in                    3 errors in setup
```

La causa dei tre errori A2 PostgreSQL è confermata: il subprocess mostra `Context impl SQLiteImpl` perché `FLASK_ENV=testing` sovrascrive l'URL PostgreSQL. Non è un difetto delle migrazioni A1: eseguendo upgrade e `db check` sullo stesso PostgreSQL con una configurazione che conserva l'URL esplicito, Alembic usa `PostgresqlImpl` e non rileva drift.

Come controllo diagnostico supplementare, sullo schema PostgreSQL sintetico sono riusciti un dry-run/apply reale con una sola sorgente e i due controlli di lock richiamati direttamente. Questi smoke test non chiudono il gate: la suite `tests/test_patient_a2_postgres.py` deve diventare eseguibile e passare senza workaround.

Il dry-run CLI reale ha inoltre confermato che l'output corrente omette conteggio sorgenti e distinzione attive/anonimizzate.

### 31.6 Gate obbligatori prima dell'accettazione A2

1. chiudere il P0 e tutti i P1 sopra elencati;
2. aggiungere i test di regressione indicati e farli fallire sulla candidata corrente prima del fix, ove praticabile;
3. eseguire la suite completa senza regressioni;
4. eseguire `tests/test_patient_a2_postgres.py` su PostgreSQL reale con **3 passed e nessuno skip/error**;
5. ripetere `flask db upgrade` e `flask db check` su SQLite e PostgreSQL, verificando esplicitamente il dialetto;
6. eseguire `git diff --check`;
7. effettuare una nuova review manuale di eccezioni/log, no-op, ownership dei recapiti, artefatti e comportamento post-commit;
8. mantenere A3–A5 fuori dalla patch e non usare dati reali.

Fino alla chiusura di questi gate, lo stato corretto è **“candidata A2 da correggere”**, non “A2 implementata localmente”.

---

## 32. Candidata PAZ-A2 v2 — hardening dopo review indipendente

> **Stato:** `In revisione`.
>
> Questa sezione descrive esclusivamente le correzioni apportate alla candidata A2 v1 dopo la revisione indipendente della sezione 31. Non autorizza apply, backfill reale, commit/push o deploy.

### 32.1 P0 chiuso nel codice candidato — sanitizzazione eccezioni

La candidata v2 introduce un confine applicativo sanitizzato per ogni errore dell'apply:

- `IntegrityError` inattesi → codice stabile `UNEXPECTED_INTEGRITY_ERROR`;
- errori inattesi non classificati → `PATIENT_BACKFILL_ERROR`;
- nessun `str(exc)`, statement SQL, parametri o `repr(exc)` attraversa il confine service/CLI;
- il rilancio usa `from None` per evitare chaining visibile;
- il `FailureResult` contiene esclusivamente run ID, conteggi e codici ammessi;
- il fallimento dell'audit secondario viene loggato solo con `run_id`, codice applicativo e nome della classe dell'errore di audit.

Test dedicati forzano errori contenenti sentinelle PII e verificano che non compaiano in:

- eccezione esposta;
- report di fallimento;
- log;
- audit DB.

La copertura CLI completa di stdout/stderr è presente in `tests/test_app.py` e richiede il runtime Flask reale per essere eseguita.

### 32.2 P1.1 chiuso — `already_synced` è un vero no-op

Il confronto dei recapiti posseduti da A2 ora comprende:

- valore display;
- valore normalizzato;
- `principale`;
- `archiviato_il`;
- `etichetta`;
- numero di recapiti attivi del tipo;
- presenza di recapiti archiviati con flag principale incoerente.

Se una proprietà posseduta differisce, l'azione è `update` e `Persona.aggiornato_il` viene aggiornato.

Quando l'azione è realmente `already_synced`, `_apply_source_projection()` restituisce immediatamente senza assegnazioni ORM, riconciliazione recapiti o modifica timestamp.

### 32.3 P1.2 chiuso — nomi legacy anomali

`analyze_legacy_source()` usa una sola normalizzazione sicura del nome prima di:

- riconoscere il placeholder privacy;
- classificare nome mancante/anomalo.

Nome troppo lungo o tipo inatteso non interrompono più il dry-run e non vengono inseriti nei messaggi di errore.

### 32.4 P1.3 chiuso nel codice/test — PostgreSQL opt-in non viene più sostituito da SQLite

`TestingConfig` mantiene SQLite in-memory come default, ma rispetta un `DATABASE_URL` esplicitamente fornito.

`tests/test_patient_a2_postgres.py` effettua inoltre un probe esplicito prima delle migration e richiede:

- `db.engine.dialect.name == 'postgresql'`;
- `current_schema()` uguale allo schema casuale creato dal test.

In questo runtime non è configurato `PAZ_A2_POSTGRES_URL`, quindi i 3 test restano correttamente skip e non vengono dichiarati superati.

### 32.5 P1.4 chiuso — plan e report non possono indicare lo stesso artefatto

La CLI confronta i path prima di leggere/scrivere con `paths_equivalent()`:

- path identici;
- path equivalenti dopo `resolve()`;
- inode identici quando entrambi esistono;
- alias tramite symlink rilevabile.

Il comando rifiuta la combinazione sia in dry-run sia in apply, indipendentemente dai flag di overwrite.

### 32.6 P1.5 chiuso — report strutturato degli apply falliti

Ogni errore dell'apply crea, **dopo il rollback**, un `ApplyResult` sanitizzato con:

- run ID;
- modalità `apply`;
- stato errore;
- `error_code` stabile;
- conteggi sorgenti;
- warning/blocker minimizzati;
- digest piano quando disponibile.

La CLI può scriverlo su `--report-file` senza mascherare l'errore applicativo principale.

### 32.7 P1.6 chiuso — audit secondario osservabile

Il fallimento dell'audit best-effort post-rollback non viene più ignorato silenziosamente.

Viene emesso esclusivamente un log minimizzato:

```text
run_id=<id tecnico>
error_code=<codice applicativo>
audit_error_type=<nome classe>
```

Non vengono loggati messaggi DB, statement o parametri.

### 32.8 P2 — contratto CLI e artefatti

Correzioni incluse:

1. `ApplyResult.report()` espone ora `source_count`, `active_sources`, `anonymized_sources` in dry-run e apply.
2. Il writer verifica `MAX_PLAN_FILE_BYTES` **prima** del rename atomico, simmetricamente al reader.
3. Sono aggiunti test limite MAX / MAX+1.
4. `tests/test_app.py` contiene test CLI reali per:
   - dry-run + apply;
   - stesso path plan/report;
   - alias symlink;
   - PII sanitizzata nella CLI;
   - report failure;
   - cancellazione piano dopo successo;
   - errore filesystem post-commit senza rollback del backfill.
5. La matrice autonoma include:
   - sorgente aggiunta dopo piano;
   - sorgente rimossa dopo piano;
   - timestamp anonimizzazione futuro;
   - rerun dopo rollback;
   - sentinelle PII;
   - dimensioni file limite.

### 32.9 P2 — modularità

La candidata v2 separa dal modulo principale almeno le due responsabilità richieste dalla review:

- `patient_backfill_artifacts.py` — file privati, canonical JSON, limiti, symlink, permessi, atomic replace/delete;
- `patient_backfill_db.py` — adapter transazionali/lock PostgreSQL e SQLite.

`patient_backfill.py` resta il service layer di dominio A2; non vengono introdotte astrazioni A3 o nuove decisioni di prodotto.

### 32.10 Evidenze riproducibili in questo runtime

Eseguito:

```text
python -m py_compile \
  patient_backfill.py \
  patient_backfill_artifacts.py \
  patient_backfill_db.py \
  patient_data.py config.py app.py \
  tests/test_patient_a2_backfill.py \
  tests/test_patient_a2_postgres.py
```

Esito: **OK**.

Suite autonoma A1+A2:

```text
pytest -q \
  tests/test_patient_data.py \
  tests/test_patient_a1_schema.py \
  tests/test_patient_a2_backfill.py \
  tests/test_patient_a2_postgres.py
```

Esito:

```text
86 passed, 3 skipped
```

I 3 skip sono soltanto i test PostgreSQL A2 perché `PAZ_A2_POSTGRES_URL` non è configurato in questo runtime.

Controllo diff:

```text
git diff --check
```

Esito: **OK**.

### 32.11 Gate ancora non verificabili in questo runtime

Non sono dichiarati superati qui:

- suite Flask completa;
- test CLI reali in `tests/test_app.py`;
- `flask --app app db upgrade` / `db check` sulla candidata v2;
- `tests/test_patient_a2_postgres.py` su PostgreSQL reale.

Il tentativo di eseguire la suite completa in questo runtime si ferma in collection con `ModuleNotFoundError: flask`. Questo è un limite dell'ambiente corrente, non viene classificato come successo né come regressione A2.

### 32.12 Gate per la prossima review

Il revisore deve eseguire sul checkout reale/virtualenv completo:

1. suite completa;
2. test CLI A2 reali;
3. `flask --app app db upgrade` e `flask --app app db check` su SQLite;
4. gli stessi controlli su PostgreSQL verificando il dialetto;
5. `tests/test_patient_a2_postgres.py` con **3 passed, nessun skip/error**;
6. nuova review manuale di:
   - sanitizzazione eccezioni/log;
   - no-op/ownership recapiti;
   - failure report;
   - artefatti post-commit;
   - lock PostgreSQL/SQLite;
   - anonimizzazione;
   - confini A2/A3.

Fino alla chiusura di questi gate, lo stato resta **`In revisione`** e nessun apply su dati reali è autorizzato.

---

## 33. Revisione indipendente della candidata PAZ-A2 v2 — 7 settembre 2026

### 33.1 Esito

La patch v2 si applica senza conflitti sopra la baseline A1 v4 indicata. Le correzioni relative a no-op, nomi anomali, distinzione plan/report, limiti degli artefatti, conteggi del report, audit secondario e adapter DB sono presenti e, nei test autonomi, funzionano.

La candidata **non è ancora accettabile**: restano due P0 di sicurezza e più P1. In particolare, la dichiarazione “P0 chiuso” della sezione 32.1 non è confermata e la copertura CLI dichiarata nella sezione 32.8 non viene eseguita dalla suite nella forma allegata. Questa sezione prevale sulle dichiarazioni di chiusura della sezione 32 dove incompatibili.

### 33.2 P0 — `TestingConfig` può indirizzare la suite verso un database reale

**Problema.** `config.py` modifica `TestingConfig.SQLALCHEMY_DATABASE_URI` affinché utilizzi qualunque `DATABASE_URL` presente nell'ambiente. `app.py` carica inoltre `.env` prima della configurazione. La fixture principale di `tests/test_app.py` esegue per ogni test:

```text
db.create_all()
...
db.drop_all()
```

Se la shell o `.env` contiene l'URL di sviluppo condiviso, staging o produzione, la suite può creare o eliminare tabelle su quel database. Il fix del test PostgreSQL A2 ha quindi ampliato pericolosamente il perimetro di tutte le prove applicative.

**Modifiche richieste.**

1. Ripristinare `TestingConfig` su SQLite in-memory in modo inderogabile, ignorando il generico `DATABASE_URL`.
2. Creare una configurazione separata e test-only per il gate PostgreSQL, attivata da una variabile dedicata, per esempio `PAZ_A2_TEST_DATABASE_URL`, e selezionata soltanto dai subprocess di `tests/test_patient_a2_postgres.py`.
3. Mantenere il probe esplicito di dialetto e schema casuale già introdotto.
4. Aggiungere un test di sicurezza in subprocess: con `FLASK_ENV=testing` e un `DATABASE_URL` arbitrario presente, l'engine deve restare `sqlite:///:memory:` e non deve tentare connessioni esterne.
5. Il gate PostgreSQL deve continuare a richiedere un opt-in esplicito e un database usa-e-getta; non deve ereditare implicitamente configurazioni ordinarie.

Questo P0 deve essere chiuso prima di rieseguire la suite in ambienti che possano contenere credenziali o URL reali.

### 33.3 P0 — l'eccezione SQL con PII resta in `__context__`

**Problema.** `apply_backfill_plan()` solleva `ApplyExecutionError(... ) from None` direttamente dentro l'`except` che ha catturato `IntegrityError`. In Python, `from None` nasconde il contesto nella stampa, ma non cancella `__context__`. La prova diretta sulla candidata restituisce:

```text
ApplyExecutionError.__context__ == IntegrityError
```

e la stringa del contesto contiene le sentinelle inserite nello statement e nei parametri. Anche la conversione in `ClickException` avviene dentro un altro `except`. I test controllano `__cause__`, messaggio, report e log, ma non percorrono `__context__`, `__cause__` e `result.exc_info`. Quindi i dati DB attraversano ancora il confine sotto forma di oggetto eccezione, anche se il terminale ordinario non li mostra.

**Modifiche richieste.**

1. Nel service catturare l'errore originale, derivare esclusivamente codice e risultato sicuri, terminare completamente il blocco `except` e soltanto dopo sollevare una nuova eccezione che non conservi riferimenti all'originale.
2. Applicare lo stesso schema al confine CLI, così la `ClickException` viene costruita e sollevata fuori dall'handler.
3. Non memorizzare l'eccezione originale nel risultato, in closure, attributi, log record o variabili che sopravvivono al blocco.
4. Aggiungere un'asserzione ricorsiva su tutta la catena `__context__`/`__cause__` e su `result.exc_info`, verificando che nessuna sentinella compaia in tipo serializzato, `str`, `repr`, `args`, statement o parametri.

Il P0 privacy della sezione 31 resta aperto fino a questa correzione.

### 33.4 P1 — i sei test CLI non invocano la CLI

**Problema.** I nuovi test passano la lista come primo argomento posizionale di `FlaskCliRunner.invoke()`:

```python
runner.invoke(args)
runner.invoke([...])
```

La lista viene interpretata come oggetto `cli`, causando `AttributeError: 'list' object has no attribute 'name'` prima che il comando venga eseguito. La suite reale produce **6 fallimenti**. Dopo la sola correzione runtime dell'invocazione emerge inoltre `NameError: logging is not defined` nel test privacy CLI.

**Modifiche richieste.**

1. Usare `runner.invoke(args=args)` negli helper e `runner.invoke(args=[...])` nei test diretti.
2. Importare esplicitamente `logging` in `tests/test_app.py`.
3. Rieseguire i sei test senza monkeypatch di compatibilità e verificare che falliscano se vengono rimossi i controlli applicativi corrispondenti.
4. Spostare il blocco `if __name__ == '__main__': pytest.main(...)` dopo tutti i test, così anche l'esecuzione diretta del file include la sezione A2.

La sezione 32.8 non può dichiarare copertura CLI finché questi test non passano normalmente.

### 33.5 P1 — i codici specifici degradano a `PATIENT_BACKFILL_ERROR`

**Problema.** `PatientBackfillError` mantiene sempre l'attributo di classe `code = "PATIENT_BACKFILL_ERROR"`; il testo passato al costruttore modifica solo il messaggio. Di conseguenza casi come:

```python
raise PatientBackfillError("A1_NOT_READY")
raise PatientBackfillError("UNSTABLE_PLAN_KEY")
raise PatientBackfillError("CODE_REVISION_UNKNOWN")
```

possono mostrare il testo corretto in CLI, ma `apply_backfill_plan()` usa `exc.code` e registra nel failure report/audit il generico `PATIENT_BACKFILL_ERROR`. Questo contraddice i codici distinti delle sezioni 24 e 32.6.

**Modifica richiesta:** usare sottoclassi dedicate oppure un costruttore con parametro `code` validato rispetto a un insieme chiuso. Messaggio CLI, `failure_result.error_code`, blocker count e audit devono concordare. Aggiungere almeno test end-to-end per `A1_NOT_READY`, `UNSTABLE_PLAN_KEY` e `CODE_REVISION_UNKNOWN`.

### 33.6 P1 — non ogni errore dell'apply produce il failure report promesso

**Problema.** Derivazione della chiave, risoluzione della revisione, accesso a `plan["summary"]` e digest avvengono prima del blocco `try` di `apply_backfill_plan()`. Inoltre la CLI risolve la revisione prima di leggere il piano. Errori come `UNSTABLE_PLAN_KEY` e `CODE_REVISION_UNKNOWN` escono quindi senza `failure_result`, senza report richiesto e senza audit best-effort.

Il report di fallimento continua inoltre a non indicare la **fase**, richiesta dalla sezione 23.

**Modifiche richieste.**

1. Estendere il confine di gestione sicura all'intera preparazione dell'apply.
2. Nella CLI leggere e validare il piano prima delle operazioni che possono fallire ma per cui serve associare run ID/report.
3. Rendere `_failure_result()` tollerante a un piano non ancora pienamente validato, senza fidarsi di campi arbitrari e senza produrre PII.
4. Aggiungere al failure report una fase stabile, per esempio `preflight`, `lock`, `revalidation`, `write` o `audit`, aggiornata prima di ogni passaggio.
5. Definire esplicitamente quali errori antecedenti alla disponibilità di un piano valido possono produrre solo un errore CLI con run ID `unknown`.
6. Testare report, audit e assenza PII per ciascuna fase.

### 33.7 P2 — completezza e manutenzione

1. **Matrice minima incompleta.** Mancano ancora prove esplicite per nome Unicode, CF valido/invalido, email invalida, chiave troppo corta o differente, tutte le mutazioni firmate richieste (azione, ID, scadenza, warning), timestamp di anonimizzazione di tipo non valido e snapshot logico completo di `PersonaCorso`.
2. **Runbook assente dalla fonte competente.** `README.md` elenca le variabili, ma `docs/OPERATIONS.md` non documenta comando, configurazione test/operativa, custodia e retention degli artefatti, gate, recovery post-commit e divieto di uso dei database ordinari nei test.
3. **Canonicalizzazione duplicata.** `canonical_json_bytes()` esiste sia in `patient_backfill.py` sia in `patient_backfill_artifacts.py`. Anche se oggi i piani validi producono gli stessi byte, firma e scrittura non dovrebbero dipendere da implementazioni parallele che possono divergere.
4. **Service ancora troppo esteso.** Dopo le due estrazioni, `patient_backfill.py` resta di circa 1.580 righe e combina schema/firma, identità runtime, analisi, pianificazione, trasformazione, audit e reporting. Ridurre ulteriormente soltanto dopo i fix P0/P1, senza introdurre scope A3.
5. **Robustezza path.** `paths_equivalent()` intercetta `OSError` ma non `RuntimeError` da loop di symlink; il controllo è fuori dal `try` della CLI. Gestire questo caso con un errore applicativo stabile e senza traceback.

### 33.8 Evidenze della review v2

Tutte le prove sono state eseguite su copia isolata e database sintetici:

```text
patch v2 sopra A1 v4                         OK, nessun conflitto
python -m py_compile                         OK
git diff --check                             OK
suite autonoma A1+A2                         86 passed, 3 skipped
suite completa, patch invariata              370 passed, 6 failed, 6 skipped
test CLI, patch invariata                    6 failed
SQLite db upgrade + db check                 OK, nessun drift
PostgreSQL A1 + A2 reale                     6 passed
smoke CLI SQLite dry-run/apply               OK
```

I sei fallimenti della suite completa sono tutti nei nuovi test CLI e avvengono prima dell'invocazione del comando. Come controllo diagnostico, correggendo **solo a runtime** la chiamata al runner e rendendo disponibile l'import `logging`, i sei test CLI passano; con le stesse due correzioni temporanee la suite raggiunge `376 passed, 6 skipped`. Questo dimostra che il percorso funzionale di base è vicino alla chiusura, ma non modifica il fatto che la patch allegata fallisce.

Il gate PostgreSQL è stato ripetuto con PostgreSQL 18.4 locale, schema casuale e URL usa-e-getta: i tre test A2 e i tre test A1 passano senza skip. Il probe conferma dialetto `postgresql` e schema atteso. Tale esito non rende sicura la modifica globale a `TestingConfig`, che resta un P0 distinto.

La prova privacy diretta ha confermato che `ApplyExecutionError.__context__` è un `IntegrityError` e contiene le sentinelle PII. Il controllo attuale di `__cause__ is None` non è sufficiente.

### 33.9 Gate prima di una candidata v3

1. chiudere entrambi i P0;
2. correggere e far passare normalmente i sei test CLI;
3. preservare i codici errore specifici in CLI, failure report e audit;
4. produrre failure report con fase per tutto il perimetro definito dell'apply;
5. completare almeno i test P2 direttamente collegati a privacy, firma e immutabilità del legacy;
6. aggiungere il runbook A2 in `docs/OPERATIONS.md`;
7. rieseguire suite completa, SQLite/PostgreSQL `db check`, test PostgreSQL opt-in e `git diff --check`;
8. ripetere una review manuale della catena delle eccezioni e della separazione tra configurazioni di test;
9. mantenere A3–A5 fuori dal perimetro e non usare dati reali.

Stato corretto dopo questa review: **`Candidata A2 v2 da correggere`**. Nessun apply su dati reali, commit/push o deploy è autorizzato da questa evidenza.

---

## 34. Candidata PAZ-A2 v3 — hardening dopo review v2

> **Stato:** `In revisione`.
>
> Questa sezione descrive esclusivamente la candidata v3 preparata dopo la review
> indipendente della sezione 33. Non autorizza apply, backfill su dati reali,
> commit/push o deploy.
>
> SHA-256 della review ricevuta e usata come baseline documentale:
> `235e6baf208393d2683c0a2a23dcdc73ba2d9ee63c7694e4d266bce8b52462a6`.

### 34.1 P0 — isolamento inderogabile della configurazione test applicativa

Correzione candidata:

- `TestingConfig.SQLALCHEMY_DATABASE_URI` è sempre `sqlite:///:memory:`;
- `TestingConfig` ignora il generico `DATABASE_URL`, anche se presente nella
  shell o caricato da `.env`;
- il gate PostgreSQL A2 usa la configurazione separata
  `paz_a2_postgres_testing`;
- tale configurazione legge esclusivamente `PAZ_A2_TEST_DATABASE_URL`;
- `app.py` rifiuta il bootstrap della configurazione dedicata se la variabile
  non è esplicita o non punta a PostgreSQL;
- `tests/test_patient_a2_postgres.py` non usa più il fallback legacy
  `PAZ_A2_POSTGRES_URL` e rimuove `DATABASE_URL` dall'ambiente dei subprocess;
- resta il probe esplicito di `postgresql` + `current_schema()` prima del gate;
- è presente un test subprocess che imposta intenzionalmente un
  `DATABASE_URL` PostgreSQL arbitrario con `FLASK_ENV=testing` e verifica che
  l'engine applicativo resti SQLite in-memory.

Questo elimina il percorso per cui `db.create_all()` / `db.drop_all()` della
suite ordinaria potevano raggiungere un database esterno.

### 34.2 P0 — eliminazione della PII dalla catena delle eccezioni

`apply_backfill_plan()` non rilancia più una eccezione sanitizzata mentre
l'eccezione DB originale è ancora attiva.

Sequenza candidata:

1. nel blocco `except` vengono estratti soltanto codice allowlisted, fase,
   eventuali blocker e conteggi minimizzati;
2. non viene conservato l'oggetto eccezione originale nel risultato, in closure
   o attributi;
3. il blocco `except` termina;
4. l'audit best-effort usa solo i primitivi sanitizzati;
5. una **nuova** eccezione applicativa viene costruita e sollevata fuori
   dall'handler.

La CLI applica la stessa regola: copia soltanto messaggio/codice/report sicuri e
solleva `ClickException` fuori dall'`except`.

I test percorrono ricorsivamente `__context__`, `__cause__` e, lato CLI,
`result.exc_info`, serializzando anche `args`, `statement` e `params` quando
presenti. Le sentinelle PII non devono risultare raggiungibili.

### 34.3 P1 — test CLI reali corretti

In `tests/test_app.py`:

- aggiunto `import logging`;
- `FlaskCliRunner.invoke()` usa `runner.invoke(args=...)`;
- il blocco `pytest.main()` è collocato dopo tutti i test;
- i test CLI coprono dry-run/apply, plan/report stesso path, alias symlink,
  failure report, sanitizzazione PII, cleanup del piano e failure filesystem
  post-commit.

Questi test non sono eseguibili nel runtime corrente perché Flask non è
installato; la review v2 ha già dimostrato che le due sole correzioni
runner/logging portavano la suite da `370 passed, 6 failed, 6 skipped` a
`376 passed, 6 skipped`. La candidata v3 deve comunque essere rieseguita nel
virtualenv reale prima di considerare chiuso il gate.

### 34.4 P1 — codici errore specifici preservati end-to-end

`PatientBackfillError` accetta ora un `code` strutturato validato su un insieme
chiuso. I call site storici che passano un codice stabile come messaggio vengono
normalizzati allo stesso codice per compatibilità.

Sono coperti almeno:

- `A1_NOT_READY`;
- `UNSTABLE_PLAN_KEY`;
- `CODE_REVISION_UNKNOWN`.

Per questi casi devono concordare:

- messaggio/codice CLI;
- `failure_result.error_code`;
- blocker count quando applicabile;
- audit fallimento.

### 34.5 P1 — failure report esteso a tutto il perimetro apply e fase esplicita

Il confine di gestione sicura di `apply_backfill_plan()` include ora anche:

- derivazione chiave;
- risoluzione code revision;
- verifica statica del piano;
- accesso ai conteggi/digest;
- acquisizione lock;
- rivalidazione DB;
- scrittura;
- audit.

Fasi stabili:

- `preflight`;
- `lock`;
- `revalidation`;
- `write`;
- `audit`.

`_failure_result()` è tollerante a un mapping piano non ancora pienamente
validato e usa soltanto campi primitivi verificati. Se il piano valido è già
stato letto, la CLI può quindi scrivere il report anche per errori come
`UNSTABLE_PLAN_KEY` e `CODE_REVISION_UNKNOWN`.

Gli errori antecedenti a qualunque piano leggibile/validabile possono produrre
soltanto un errore CLI sanitizzato, perché non esiste ancora un `run_id`
affidabile da associare al report.

Test autonomi coprono esplicitamente almeno `preflight`, `lock`,
`revalidation`, `write` e `audit`.

### 34.6 P2 — matrice minima completata

Sono aggiunte prove esplicite per:

- nome Unicode;
- CF memorizzabile e non memorizzabile;
- email invalida;
- chiave troppo corta;
- piano verificato con chiave differente;
- tamper firmato su azione, legacy ID, scadenza e warning;
- timestamp anonimizzazione futuro e tipo invalido;
- fingerprint source sensibile a tutti i campi business legacy A2;
- sorgente aggiunta/rimossa dopo il piano;
- rerun dopo rollback;
- symlink loop nei path;
- fasi di errore lock/audit;
- isolamento di `TestingConfig` da `DATABASE_URL`.

### 34.7 P2 — runbook nella fonte operativa

`docs/OPERATIONS.md` contiene ora una sezione PAZ-A2 candidata con:

- configurazione sicura dei database di test;
- uso esclusivo di `PAZ_A2_TEST_DATABASE_URL` per PostgreSQL opt-in;
- gate `db upgrade` / `db check` / pytest / diff;
- comandi dry-run/apply;
- custodia, permessi e retention di piano/report;
- recovery per errori filesystem successivi al commit;
- divieto di database ordinari/reali nei test;
- confini A2/A3.

Il `README.md` segnala la variabile test dedicata senza sostituirla al normale
`DATABASE_URL` operativo.

### 34.8 P2 — canonicalizzazione unica e modularità

La canonicalizzazione JSON esiste in una sola implementazione:
`patient_backfill_artifacts.canonical_json_bytes`. Il service la re-esporta per
compatibilità ma non ne mantiene una copia.

La candidata v3 separa inoltre:

- `patient_backfill_artifacts.py` — file privati/canonicalizzazione;
- `patient_backfill_db.py` — transazioni e lock DB;
- `patient_backfill_plan.py` — contratto piano, firma/HMAC, schema, code revision,
  identità ambiente/database e revisione Alembic;
- `patient_backfill.py` — analisi del dominio A2 e orchestrazione apply.

Il service principale scende da circa 1.700 a circa 1.360 righe senza introdurre
scope A3 o modificare il contratto A2.

`paths_equivalent()` gestisce inoltre `RuntimeError` da loop di symlink senza
propagare traceback.

### 34.9 Evidenze riproducibili in questo runtime

Eseguiti dopo i fix P0/P1/P2 e il refactor del piano:

```text
python -m py_compile \
  patient_backfill.py patient_backfill_plan.py \
  patient_backfill_artifacts.py patient_backfill_db.py \
  patient_data.py config.py app.py \
  tests/test_patient_a2_backfill.py \
  tests/test_patient_a2_postgres.py tests/test_app.py
```

Esito: `OK`.

Suite A2 autonoma SQLite:

```text
pytest -q tests/test_patient_a2_backfill.py
60 passed
```

Suite autonoma A1+A2:

```text
pytest -q \
  tests/test_patient_data.py \
  tests/test_patient_a1_schema.py \
  tests/test_patient_a2_backfill.py \
  tests/test_patient_a2_postgres.py
```

Esito della suite autonoma A1+A2 senza i test PostgreSQL A1: `102 passed, 3 skipped`; i 3 skip sono i test PostgreSQL A2. Eseguendo anche `tests/test_patient_a1_postgres.py`, il conteggio complessivo opt-in è `102 passed, 6 skipped`: 3 skip A1 PostgreSQL + 3 skip A2 PostgreSQL, perché in questo runtime non è configurato alcun database PostgreSQL di test.

### 34.10 Gate che restano obbligatori nel checkout reale

Il runtime corrente non dispone di Flask/Flask-SQLAlchemy/Flask-Migrate/psycopg;
non vengono quindi dichiarati superati qui:

1. suite Flask completa, inclusi i test CLI A2;
2. `flask --app app db upgrade` + `db check` su SQLite;
3. gli stessi gate su PostgreSQL con dialetto/schema verificati;
4. `tests/test_patient_a2_postgres.py` con 3 pass e nessuno skip/error;
5. nuova review manuale della catena eccezioni e separazione delle configurazioni
   di test.

L'evidenza della review v2 secondo cui PostgreSQL A1+A2 reale aveva `6 passed`
resta una prova sulla **v2**, non viene automaticamente attribuita alla v3.

### 34.11 Stato

La candidata v3 chiude nel sorgente i rilievi noti della review v2, ma resta
**`In revisione`** fino alla ripetizione dei gate del punto 34.10 nel checkout
reale. Nessun apply su dati reali è autorizzato.

---

## 35. Revisione indipendente della candidata PAZ-A2 v3 — 7 settembre 2026

### 35.1 Esito e perimetro

La patch v3 si applica senza conflitti sopra la baseline dichiarata
`ebab09b` + PAZ-A1 v4. La review è stata eseguita in una copia isolata; non
dimostra che A1 o A2 siano integrate nel repository reale e non autorizza
commit, deploy o uso di dati reali.

I due P0 della sezione 33 risultano chiusi: la configurazione applicativa
`testing` resta SQLite in-memory anche in presenza di un `DATABASE_URL`
PostgreSQL, mentre la configurazione PostgreSQL A2 è separata e opt-in; inoltre
le eccezioni sanitizzate del service e della CLI vengono sollevate fuori dai
rispettivi handler e i test non rendono raggiungibile l'`IntegrityError`
contenente le sentinelle PII tramite `__context__`, `__cause__` o
`result.exc_info`.

La candidata **non è ancora accettabile**: resta un P1 nel failure report dei
blocker applicativi. Questa sezione prevale sulla dichiarazione di chiusura
integrale della sezione 34.11 dove incompatibile.

### 35.2 Standards

#### P2 — residui meccanici del refactor

`patient_backfill.py` importa `canonical_json_bytes` sia da
`patient_backfill_artifacts` sia da `patient_backfill_plan`, lasciando che il
secondo import nasconda il primo. Restano inoltre import non usati dopo
l'estrazione (`timezone`, `Path`, `subprocess`, `text`, `URL` e
`PLAN_KEY_CONTEXT`) e tre ampi blocchi di righe vuote/commenti di sezione senza
contenuto. In `patient_backfill_plan.py` restano almeno `json` e `Sequence` non
usati.

Non è un difetto funzionale, ma rende meno leggibile il confine fra service,
piano e artefatti e può mascherare future divergenze del re-export. Rimuovere
gli import e gli spazi residui; mantenere una sola importazione esplicita per
ogni simbolo re-esportato. Questo P2 non blocca da solo il passaggio ad A2.

### 35.3 Spec

#### P1 — il failure report perde i codici blocker effettivi

Quando `_assert_apply_plan_static()` incontra blocker già presenti nel piano,
solleva `BackfillBlockerError` con i codici specifici. Nel relativo handler,
però, `_safe_error_code()` restituisce `BACKFILL_BLOCKER` e
`_failure_result()` costruisce sempre:

```json
{"blockers": {"BACKFILL_BLOCKER": 1}, "error_code": "BACKFILL_BLOCKER"}
```

I codici reali vengono conservati soltanto in `failure_blocker_codes` per
ricostruire il messaggio dell'eccezione, ma non entrano nel report né
nell'audit. La prova diretta con
`ANONYMIZED_SOURCE_HAS_RESIDUAL_PII` ha prodotto:

```text
plan_blockers {'ANONYMIZED_SOURCE_HAS_RESIDUAL_PII': 1}
exception_blockers ('ANONYMIZED_SOURCE_HAS_RESIDUAL_PII',)
failure_report_blockers {'BACKFILL_BLOCKER': 1}
```

Questo contraddice la sezione 25, che richiede conteggi per codice blocker, e
lascia incompleta la coerenza end-to-end richiesta dalla sezione 33.5. Il
wrapper `error_code = BACKFILL_BLOCKER` può restare, perché un piano può avere
più blocker; il campo `blockers` deve però contenere i codici allowlisted reali
e i rispettivi conteggi. L'audit minimizzato deve conservarne almeno l'elenco
ordinato, senza valori sorgente.

Modifica richiesta:

1. passare a `_failure_result()` una mappa derivata esclusivamente da
   `BackfillBlockerError.blocker_codes`, validata contro `BLOCKER_CODES`;
2. usare `{"BACKFILL_BLOCKER": 1}` soltanto se non è disponibile alcun codice
   specifico sicuro;
3. aggiungere un test service e uno CLI con almeno un blocker di piano, che
   verifichino coerenza fra piano, failure report, output e audit, oltre
   all'assenza di PII.

### 35.4 Evidenze ripetute durante questa review

- `python -m py_compile ...`: superato;
- suite autonoma A1+A2: `102 passed, 6 skipped` senza URL PostgreSQL;
- suite completa: `396 passed, 6 skipped`;
- SQLite reale: `flask --app app db upgrade` superato;
- SQLite reale: `flask --app app db check` →
  `No new upgrade operations detected`;
- PostgreSQL 18.4 locale usa-e-getta, con probe dialetto/schema e migrazioni:
  test A1+A2 `6 passed` senza skip;
- `git diff --check` sulla tranche A2 rispetto ad A1 v4: superato;
- SHA-256 della patch revisionata:
  `f96fafa89b7bc9eb84d40c34d46560c7cc0211e199ffd8f4cf7de70e4e606a51`.

I sei skip della suite completa sono soltanto i gate PostgreSQL opt-in A1/A2,
che sono stati poi eseguiti separatamente con esito positivo.

### 35.5 Gate prima di A2

1. correggere il P1 della sezione 35.3;
2. aggiungere e superare i test service/CLI sul dettaglio dei blocker;
3. rieseguire suite completa, SQLite `db upgrade`/`db check`, PostgreSQL A1+A2
   e `git diff --check` sulla patch corretta;
4. ripetere la review del delta minimo.

Il P2 della sezione 35.2 può essere corretto nello stesso delta, ma non deve
ampliare il perimetro funzionale oltre PAZ-A2.

---

## 36. Candidata PAZ-A2 v4 — delta minimo dopo review v3

> **Stato:** `In revisione`.
>
> Questa sezione descrive esclusivamente il delta richiesto dalla review della
> candidata v3. Non amplia PAZ-A2 e non autorizza apply su dati reali, commit,
> push o deploy.

### 36.1 P1 chiuso nel sorgente — blocker specifici preservati end-to-end

La v4 mantiene `error_code = BACKFILL_BLOCKER` come wrapper quando un apply è
fermato da uno o più blocker di piano, ma il campo `blockers` del failure report
non viene più sostituito dal wrapper generico.

La nuova funzione `_safe_blocker_counts()`:

- accetta esclusivamente i codici presenti in `BackfillBlockerError.blocker_codes`;
- filtra i codici contro l'allowlist `BLOCKER_CODES`;
- recupera dal `summary.blockers` firmato il conteggio del codice quando
  disponibile;
- usa conteggio `1` per un blocker sicuro emerso nella rilettura sotto lock ma
  non presente nel piano;
- usa `{"BACKFILL_BLOCKER": 1}` soltanto quando non esiste alcun codice
  specifico allowlisted sicuro.

`_failure_result()` riceve ora esplicitamente la mappa dei blocker sanitizzati.
Il risultato può quindi essere, per esempio:

```json
{
  "error_code": "BACKFILL_BLOCKER",
  "blockers": {
    "ANONYMIZED_SOURCE_HAS_RESIDUAL_PII": 2
  }
}
```

senza inserire nel report alcun valore sorgente.

L'audit di errore post-rollback conserva inoltre il solo elenco ordinato
`blocker_codes`. Non memorizza nomi, recapiti, CF, note, statement SQL o
parametri.

`BackfillBlockerError` filtra a sua volta i codici ricevuti contro
`BLOCKER_CODES`; se nessun codice è sicuro espone soltanto il wrapper generico.

### 36.2 Test di regressione aggiunti

#### Service

`tests/test_patient_a2_backfill.py` aggiunge un caso con due sorgenti legacy
anonimizzate ma contenenti un recapito residuo.

Il test verifica che:

- il piano contenga
  `ANONYMIZED_SOURCE_HAS_RESIDUAL_PII: 2`;
- l'eccezione esponga `BACKFILL_BLOCKER` come wrapper;
- il failure report conservi
  `ANONYMIZED_SOURCE_HAS_RESIDUAL_PII: 2`;
- l'audit contenga il codice blocker specifico in `blocker_codes`;
- il recapito sentinella non compaia né nel report né nell'audit.

#### CLI

`tests/test_app.py` aggiunge un caso end-to-end con un piano bloccato da
`ANONYMIZED_SOURCE_HAS_RESIDUAL_PII`.

Il test verifica che:

- il dry-run generi il blocker specifico;
- l'apply fallisca senza cancellare il piano;
- l'output CLI esponga il codice blocker e non il recapito sentinella;
- il failure report mantenga la mappa blocker specifica;
- l'audit contenga il codice specifico;
- nessuna PII sentinella compaia in output/report/audit.

### 36.3 P2 chiuso — pulizia del refactor

Il delta rimuove i residui meccanici segnalati dalla review:

- eliminato l'import duplicato di `canonical_json_bytes` nel service;
- rimossi da `patient_backfill.py` gli import non usati `timezone`, `Path`,
  `subprocess`, `text`, `URL` e `PLAN_KEY_CONTEXT`;
- rimossi da `patient_backfill_plan.py` `json` e `Sequence` non usati;
- eliminati i blocchi di commenti/righe vuote rimasti dalle estrazioni;
- mantenuta una sola implementazione della canonicalizzazione in
  `patient_backfill_artifacts.py` e un solo import esplicito nel service per il
  re-export compatibile.

Nessun comportamento A3–A5 è stato introdotto.

### 36.4 Evidenze riproducibili in questo runtime

Eseguito sulla candidata v4 in copia isolata:

```text
python -m py_compile ...                     OK
tests/test_patient_a2_backfill.py            61 passed
suite autonoma A1+A2                         103 passed, 6 skipped
git diff --check                             OK
```

I sei skip della suite autonoma sono i tre test PostgreSQL opt-in A1 e i tre
A2, perché in questo runtime non è disponibile PostgreSQL/psycopg.

Questo ambiente non dispone di Flask/Flask-SQLAlchemy/Flask-Migrate; non vengono
quindi attribuiti alla v4 gli esiti della suite completa o dei test CLI, anche
se il file di test compila correttamente.

### 36.5 Gate per la review finale della v4

Il revisore deve ripetere sul checkout completo:

1. suite completa, inclusi i nuovi test CLI blocker;
2. suite autonoma A1+A2;
3. SQLite `flask --app app db upgrade` e `flask --app app db check`;
4. PostgreSQL A1+A2 opt-in con database usa-e-getta e probe dialetto/schema;
5. `git diff --check`;
6. review manuale del delta minimo, in particolare coerenza
   piano → eccezione → failure report → audit per i blocker specifici.

Fino alla chiusura di questi gate, lo stato resta **`In revisione`** e nessun
apply su dati reali è autorizzato.

---

## 37. Revisione indipendente della candidata PAZ-A2 v4 — 7 settembre 2026

### 37.1 Esito e perimetro

La patch v4 si applica senza conflitti sopra la baseline dichiarata
`ebab09b` + PAZ-A1 v4. La review è stata svolta in una copia isolata e non
modifica lo stato del repository reale, nel quale PAZ-A1/A2 non risultano
integrate.

Il P1 della sezione 35.3 risulta chiuso: il wrapper resta correttamente
`BACKFILL_BLOCKER`, mentre failure report e audit conservano i codici blocker
specifici allowlisted. I test service e CLI verificano anche conteggi superiori
a uno e assenza delle sentinelle PII.

Non sono emersi P0 o P1. La candidata è quindi **accettabile rispetto alla
specifica PAZ-A2**, fermi restando il carattere di proposta, l'integrazione
ordinata di PAZ-A1 e le autorizzazioni separate per commit, deploy o dati reali.
Restano due P2 di manutenzione che è opportuno chiudere nel delta minimo prima
dell'integrazione, senza riaprire il perimetro funzionale.

### 37.2 Standards

#### P2.1 — due intestazioni vuote sono rimaste nel service

In `patient_backfill.py`, subito prima della sezione reale
`Source/target projections and privacy analysis`, restano le intestazioni
`Pure helpers: time, canonical JSON, HMAC and plan schema` e
`Runtime identity: code revision, environment/database and Alembic` senza
alcun codice sottostante.

Sono residui dell'estrazione verso `patient_backfill_plan.py`; vanno rimossi.
La frase della sezione 36.3 secondo cui tutti i blocchi di commenti/righe vuote
sono stati eliminati non è quindi completamente corretta.

#### P2.2 — allowlist e classificazione degli errori restano duplicate

L'insieme dei codici sicuri viene ricostruito in più punti fra
`patient_backfill_plan.PatientBackfillError`,
`patient_backfill.ApplyExecutionError` e `_safe_error_code()`; la factory
`_sanitized_exception_for_code()` mantiene inoltre una mappa separata delle
sottoclassi.

Non produce un errore nella candidata attuale, ma aggiungere o riclassificare
un codice richiede modifiche coordinate e può causare un fallback silenzioso a
`PATIENT_BACKFILL_ERROR`. Centralizzare nel modulo del contratto una sola
allowlist/classificazione degli errori sicuri, mantenendo l'estrazione piccola
e senza introdurre architettura A3–A5.

### 37.3 Spec

Nessun rilievo azionabile.

In particolare:

- `_safe_blocker_counts()` filtra contro `BLOCKER_CODES` e recupera dal piano
  firmato il conteggio specifico;
- il fallback `{"BACKFILL_BLOCKER": 1}` viene usato soltanto in assenza di un
  codice sicuro;
- l'audit memorizza esclusivamente l'elenco ordinato dei codici blocker;
- service, CLI, report e audit concordano sul codice specifico senza esporre
  recapiti o altri dati sorgente;
- non è stato introdotto scope A3–A5.

### 37.4 Evidenze ripetute durante questa review

- `python -m py_compile ...`: superato;
- `tests/test_patient_a2_backfill.py` più il test CLI blocker:
  `62 passed`;
- suite autonoma A1+A2: `103 passed, 6 skipped` senza URL PostgreSQL;
- suite completa: `398 passed, 6 skipped`;
- SQLite reale: `flask --app app db upgrade` superato;
- SQLite reale: `flask --app app db check` →
  `No new upgrade operations detected`;
- PostgreSQL 18.4 locale usa-e-getta, con probe dialetto/schema e migrazioni:
  test A1+A2 `6 passed` senza skip;
- `git diff --check` sulla tranche A2 rispetto ad A1 v4: superato;
- SHA-256 della patch revisionata:
  `d321a626dcc0e4269404d964bb75e3ef71399d0524a84257f746a4074f18566f`.

I sei skip della suite completa sono esclusivamente i gate PostgreSQL opt-in
A1/A2, eseguiti poi separatamente con esito positivo.

### 37.5 Stato e prossimo passaggio

La candidata v4 chiude tutti i P0/P1 noti di PAZ-A2. Prima dell'integrazione è
raccomandato un ultimo delta solo manutentivo per i due P2 della sezione 37.2,
seguito da compilazione, suite completa e `git diff --check`.

L'integrazione deve comunque rispettare l'ordine PAZ-A1 → PAZ-A2 e richiede una
decisione esplicita separata. Questa review non autorizza apply su dati reali,
commit, push o deploy.

---

## 38. Candidata PAZ-A2 v5 — cleanup manutentivo dopo accettazione v4

> **Stato:** `In revisione` per delta manutentivo.
>
> La review della v4 ha chiuso tutti i P0/P1 noti e non ha rilevato scostamenti dalla specifica A2. Restavano soltanto due P2 di manutenzione: intestazioni vuote residue del refactor e duplicazione della classificazione/allowlist degli errori. La v5 corregge esclusivamente questi due punti e non modifica il comportamento funzionale di PAZ-A2.

### 38.1 P2 — intestazioni vuote del refactor

Rimosse da `patient_backfill.py` le due intestazioni di sezione rimaste senza contenuto dopo l'estrazione delle responsabilità in `patient_backfill_plan.py`.

Non vengono spostate funzioni e non cambia alcun percorso di esecuzione.

### 38.2 P2 — contratto errori centralizzato

La candidata v4 ricostruiva in più punti la combinazione fra `BLOCKER_CODES` e i codici wrapper `PATIENT_BACKFILL_ERROR` / `BACKFILL_BLOCKER`.

La v5 centralizza il contratto in `patient_backfill_plan.py`:

- `GENERAL_ERROR_CODES` contiene esclusivamente i wrapper generici;
- `ERROR_CODES = BLOCKER_CODES | GENERAL_ERROR_CODES` è l'unica allowlist complessiva;
- `sanitize_error_code()` normalizza i codici applicativi;
- `sanitize_blocker_codes()` filtra e ordina esclusivamente blocker allowlisted.

`PatientBackfillError`, `BackfillBlockerError`, `ApplyExecutionError`, `_safe_error_code()` e `_safe_blocker_counts()` riusano questi helper invece di ricostruire allowlist locali.

La conversione finale codice → tipo di eccezione resta nel service perché `ApplyExecutionError` contiene un `ApplyResult` ed è quindi una responsabilità dell'orchestrazione apply, non del contratto del piano.

### 38.3 Invarianti funzionali mantenute

Il cleanup non modifica:

- firma o canonicalizzazione del piano;
- schema/TTL/fingerprint;
- codici P0/P1 già verificati;
- failure report e conteggi blocker specifici;
- audit minimizzato;
- lock SQLite/PostgreSQL;
- idempotenza;
- anonimizzazione;
- CLI;
- confini A2/A3;
- schema DB o migration.

### 38.4 Evidenze della review v4

La review indipendente della v4 ha registrato, sulla patch v4 invariata:

```text
suite completa                               398 passed, 6 skipped
suite autonoma A1+A2                         103 passed, 6 skipped
test mirati service/CLI                      62 passed
PostgreSQL reale usa-e-getta                 6 passed
SQLite db upgrade + db check                 OK
python compile                               OK
git diff --check                             OK
```

Queste evidenze appartengono alla **v4** e non vengono attribuite automaticamente alla v5.

### 38.5 Evidenze riproducibili sulla v5 in questo runtime

Eseguito:

```text
python -m py_compile patient_backfill.py patient_backfill_plan.py \
  patient_backfill_artifacts.py patient_backfill_db.py
OK

pytest -q tests/test_patient_a2_backfill.py tests/test_patient_data.py \
  tests/test_patient_a1_schema.py tests/test_patient_a1_postgres.py \
  tests/test_patient_a2_postgres.py
103 passed, 6 skipped
```

I 6 skip sono i test PostgreSQL opt-in A1/A2 non configurati in questo runtime.

Prima dell'accettazione definitiva del delta v5 il revisore deve ripetere almeno:

1. suite completa;
2. test mirati service/CLI;
3. PostgreSQL reale A1+A2;
4. SQLite `db upgrade` + `db check`;
5. `git diff --check`;
6. review manuale del solo delta v4 → v5.

### 38.6 Stato

La v5 non riapre alcun rilievo di specifica e non introduce nuove funzionalità. Resta `In revisione` esclusivamente per la verifica del delta manutentivo. Nessun apply su dati reali, commit/push o deploy è autorizzato da questo pacchetto.

---

## 39. PAZ-A4 — cutover diretto approvato per il database vuoto

> **Stato:** implementato nel branch candidato; collaudo privato Render e
> go-live non ancora autorizzati.

La decisione D-117 elimina il dual-write: dal lancio ogni nuova anagrafica e
ogni nuovo collegamento vengono scritti soltanto nel modello Pazienti 2.0. Le
tabelle legacy restano nello schema per compatibilità e non vengono cancellate
in questa fase.

### 39.1 Perimetro implementato

- elenco, ricerca, creazione, modifica e scheda admin usano `Persona` e
  `RecapitoPersona`;
- appuntamenti, call sonno e iscrizioni corso valorizzano le rispettive FK v2;
- il flusso operativo non crea più `PersonaCorso` o `CollegamentoPersona`;
- storico, ricerca dei possibili duplicati e consensi privacy leggono il modello
  v2, mantenendo una sola compatibilità di lettura per eventuali record legacy;
- la retention rimuove i collegamenti v2 e anonimizza la persona quando non ha
  più pratiche identificabili;
- la migrazione `d4a7c2e9f610` aggiunge il collegamento v2 ai consensi e impone
  che ogni consenso punti a un solo modello, legacy oppure v2;
- il downgrade è intenzionalmente bloccato dopo la prima scrittura A4, perché
  non esiste una ricostruzione affidabile dei nuovi pazienti nel legacy.

### 39.2 PAZ-A3 sul database dichiarato vuoto

Il comando `flask --app app patients preflight-cutover` verifica la revisione
Alembic e stampa esclusivamente conteggi minimizzati. Deve restituire revisione
`d4a7c2e9f610`, `status: pronto` e tutti i conteggi a zero. In caso contrario il
deploy si ferma: non viene avviato automaticamente il backfill A2.

La procedura completa e i criteri di arresto sono nella sezione PAZ-A3/A4 di
`OPERATIONS.md`.

### 39.3 Evidenze locali del 10 settembre 2026

```text
suite completa Python                         410 passed, 6 skipped
suite JavaScript                              37 passed
PostgreSQL reale usa-e-getta A1/A2            6 passed
migrazione A4 + db check PostgreSQL reale     OK
migrazione A4 + db check SQLite               OK
preflight A3 su database SQLite vuoto         pronto, tutti i conteggi a zero
python compile + git diff --check             OK
```

Il collaudo visuale con dati esclusivamente sintetici ha verificato elenco,
modulo e scheda a 1440×900 e 390×844 px senza overflow orizzontale. Il test
reale nel browser locale `logout → Indietro` ha richiesto nuovamente
l'autenticazione e non ha ripresentato la scheda protetta. Database e server di
collaudo sono stati eliminati al termine.

Restano esterni a queste evidenze il deploy privato Render, il preflight sul
database Render, gli smoke test post-deploy e il go-live pubblico.
