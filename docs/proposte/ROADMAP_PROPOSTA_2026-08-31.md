# Roadmap — proposta di aggiornamento del 31 agosto 2026

> **Documento di revisione, non applicato alla repository.**
>
> Base di riferimento: `docs/ROADMAP.md` della `main` corrente.
> Le sezioni e gli step 1–20 esistenti restano invariati.
> Questo file contiene esclusivamente gli aggiornamenti da integrare nella roadmap corrente.
> I file originali della repository non sono stati modificati.

## Aggiornamento della revisione documentale

Sostituire l’intestazione iniziale:

`Revisione documentale: 29 agosto 2026.`

con:

`Revisione documentale: 31 agosto 2026.`

Le evidenze operative già datate restano tali: il cambio della data documentale non trasforma automaticamente test locali o collaudi precedenti in verifiche post-deploy.

## Vincolo sequenziale per l’evoluzione dell’area Pazienti

Aggiungere dopo `## Criterio di priorità`:

> **Vincolo approvato il 31 agosto 2026:** prima di modificare il modello dati dell’anagrafica, la Scheda Paziente o introdurre cartella infermieristica, lettore Tessera Sanitaria, documenti clinici o promemoria, completare e superare tutti i test e i collaudi delle funzioni attualmente implementate. L’evoluzione dell’area Pazienti non deve interferire con la chiusura dei P0/P1 correnti.
>
> Fino a quel momento l’area Pazienti esistente resta invariata salvo correzioni necessarie alla chiusura dei collaudi. Le nuove funzioni gestionali restano P2 e non vengono anticipate nel piano operativo numerato 1–20.

## Dopo il lancio

### P2 — validazione e ottimizzazione

Mantenere invariata la sezione corrente.

### P2 — estensioni del gestionale

Sostituire la voce attuale sul multiaccount con il seguente piano:

1. **Nuovo modello anagrafico `Persona`.**
   - Migrazione funzionale da `PersonaCorso`, non rinomina isolata.
   - Nome e cognome separati; data di nascita, sesso, luogo di nascita e residenza strutturati con campi non obbligatori dove approvato.
   - Relazioni esplicite tra minori e adulti/tutori.
   - Gestione dei duplicati con confronto forte sul CF, avviso su almeno due campi deboli coincidenti, `Unisci anagrafica` / `Non unire`, fusione reversibile e auditata.

2. **Scheda Paziente 2.0.**
   - `Panoramica`, `Anagrafica`, `Attività`, `Cartella infermieristica`, `Note`, `Consensi e documenti`.
   - Azioni rapide con anagrafica preselezionata.
   - Timeline unica con `Prestazioni sanitarie` e `Servizi / corsi` attivi di default; `Amministrative` disponibile ma nascosto di default.
   - Ricerca globale.

3. **Note e Cartella infermieristica.**
   - Note amministrative e cliniche versionate.
   - Anamnesi strutturata + testo libero.
   - Condizioni attive/pregresse, allergie, farmaci, terapie infermieristiche, dispositivi, medicazioni/lesioni e fotografie cliniche collegate.
   - Nessun tracciamento longitudinale dei parametri vitali nella prima versione.
   - Ricerca interna.
   - Prestazione eseguita distinta dall’appuntamento e precompilata quando deriva da una prenotazione.
   - Referti distinti dagli allegati e coda `Referti da verificare/associare`.

4. **Lettore Tessera Sanitaria v1.**
   - Banda magnetica USB + barcode.
   - Niente chip CNS nella prima versione.
   - `Lettura → anteprima → controllo duplicati → conferma`.
   - Nessun salvataggio della traccia grezza.
   - Uso anche come ricerca rapida del paziente.

5. **Documenti e Google Drive.**
   - File fisici su Drive, metadati e relazioni nel database.
   - Cartella paziente identificata solo dall’ID interno, organizzata per anno e categoria.
   - Versionamento, drag-and-drop, tipi controllati, limite 25 MB.
   - Apertura diretta dalla scheda paziente.
   - Cestino/archivio recuperabile per 90 giorni con audit.
   - Conservazione differenziata per categoria e gestione delle scadenze.

6. **Consensi e firma.**
   - Conservazione della versione esatta del documento accettato.
   - Consenso web e upload del cartaceo firmato.
   - Implementazione successiva della tavoletta per firma; hardware da scegliere.
   - Documento completo mostrato prima della firma.
   - PDF firmato con data/ora; firma non conservata come immagine separata riutilizzabile.
   - Copia via email su richiesta.

7. **Scanner e acquisizione mobile.**
   - Acquisizione diretta da scanner.
   - Acquisizione sicura da smartphone.
   - Suggerimento automatico di paziente e categoria sempre soggetto a conferma.

8. **Promemoria paziente.**
   - Area `Da fare` con attività manuali e avvisi automatici.
   - Avvisi chiudibili con `Non mostrare più`.
   - Sincronizzazione obbligatoria su Google Calendar e visualizzazione nell’agenda locale.
   - Eventi all-day, liberi/trasparenti e sempre esclusi dal calcolo degli slot prenotabili.

**Vincoli trasversali**
- Il gestionale resta mono-professionista: non pianificare multiaccount, ruoli o assegnazioni tra operatori.
- Nessuna delle estensioni sopra parte prima della chiusura positiva dei test e dei collaudi correnti.
- Prima di usare cartella infermieristica, fotografie cliniche, documenti sanitari o firma con dati reali, chiudere la progettazione di sicurezza, privacy, audit, conservazione e backup pertinente.
- Ogni modifica di schema usa Alembic, test di migrazione, verifica dei collegamenti storici e piano di rollback.

### P2 — pagamenti

Mantenere invariata la sezione corrente.

## Aggiornamento della roadmap

Mantenere la regola corrente e aggiungere:

> Le estensioni dell’area Pazienti seguono D-106 e non devono essere avviate mentre restano incompleti i test e i collaudi delle funzioni già implementate. Le decisioni D-107–D-115 descrivono l’architettura futura ma non autorizzano modifiche immediate al codice.
