# Area Pazienti 2.0 — specifica corrente e registro di revisione

> **Stato al 7 settembre 2026:** candidata `PAZ-A1 v4` verificata tecnicamente in copia isolata; applicazione al repository ancora separata.
>
> Questo documento è la fonte di handoff della candidata **PAZ-A1 v4**. La patch non è applicata al repository, non è committata, non è deployata e non autorizza A2, backfill o uso di dati reali.
>
> La base verificata è `ebab09b`. La patch v4 si applica pulitamente a tale commit; HEAD Git e head Alembic devono essere ricontrollati prima dell'applicazione effettiva.

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
| PAZ-A3 | legacy + confronto | popolate solo da mapping verificato |
| PAZ-A4 | da decidere | eventuale dual-read/dual-write limitato |
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

Da progettare dopo A1–A3.

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
