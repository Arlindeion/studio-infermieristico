# Backup Windows — installazione guidata

Pacchetto preparato il 21 ottobre 2026 per Windows 11 Pro 25H2, PowerShell 5.1
e PostgreSQL 18.6. **Aggiornamento 22 ottobre 2026:** installazione, backup cifrato reale, restore locale isolato e attività pianificata con wrapper monitor verificati tramite gli esiti del committente. Due segnali distinti Mac/Windows ed email tecnica verificati; dettagli e limiti in [OPERATIONS.md](../../docs/OPERATIONS.md#backup-e-ripristino-postgresql), D-128–D-129. Le istruzioni seguenti servono per installazione/manutenzione, non richiedono di reinstallare il PC già configurato. Il pacchetto non modifica Calendar; monitor e backup non ricevono dati via email.

## Contenuto

- `Initialize-Backup.ps1`: prepara cartelle private, chiave age e configurazione locale.
- `Backup.ps1`: crea il backup cifrato; con `-Check` controlla la copia senza collegarsi al database.
- `Verify-Archive.ps1`: prova decifratura e lettura della struttura del dump, senza modificarne il database.
- `StudioBackup.psm1`: funzioni condivise. Deve restare accanto agli altri script.

## 1. Installare soltanto lo strumento di cifratura

In PowerShell, sul PC Windows:

```powershell
winget install --id FiloSottile.age --exact --source winget
```

È il comando indicato dal [progetto age](https://github.com/FiloSottile/age).
Chiudere e riaprire PowerShell, poi verificare:

```powershell
age --version
age-keygen --version
```

Non servono Java, un server PostgreSQL locale, Python o moduli PowerShell esterni.
La cifratura age è autenticata e leggibile anche su Mac con age: nessuna
implementazione crittografica personalizzata e nessuna password di cifratura
negli argomenti del processo automatico.

## 2. Copiare i file

Estrarre il pacchetto e copiare i quattro file `.ps1`/`.psm1` nella cartella
già creata:

```text
C:\SCStudioBackup\scripts\
    Initialize-Backup.ps1
    Backup.ps1
    Verify-Archive.ps1
    StudioBackup.psm1
```

Non salvare la cartella in OneDrive o in una condivisione. Non inserire chiavi,
URL privati o credenziali nel repository, nella chat o nei file degli script.
Non usare `ExecutionPolicy Bypass` o disattivare protezioni globali: se Windows
blocca lo script, fermarsi, verificare origine e file e riportare il messaggio
senza dati riservati. Non avviare gli script scaricati da fonti diverse dal
pacchetto del progetto.

## 3. Prima della configurazione

BitLocker del disco C: risulta attivo dal controllo comunicato dall'utente;
conservare separatamente anche la sua chiave di recupero. Il dump non cifrato
esiste temporaneamente nella cartella privata `.work`, prima della cifratura.
La cancellazione del temporaneo non equivale a cancellazione forense sicura:
la cifratura del disco rimane necessaria.

Concordare l'accesso al database Render dalla sola rete autorizzata. Non aprire
PostgreSQL a `0.0.0.0/0`; con IP variabile definire un accesso controllato.
Non collegare mai questo pacchetto a un database diverso da quello esplicitamente
approvato. Preferire credenziali dedicate con i permessi necessari al dump;
la loro creazione e l'abilitazione della rete non sono eseguite dagli script.

Serviranno host **esterno** Render, nome database, utente e password. La password
va digitata solo nel prompt nascosto dello script sul PC, mai nei comandi o in
chat. Non incollare la stringa completa di connessione nei campi testuali.

## 4. Configurazione locale, senza connessione a Render

Usare l'account Windows che eseguirà anche l'attività pianificata. Se possibile,
aprire PowerShell come amministratore **con quello stesso account** per registrare
anche la sorgente del registro eventi. Non usare un altro account amministrativo:
le credenziali protette sono legate all'utente e al computer.

```powershell
& "C:\SCStudioBackup\scripts\Initialize-Backup.ps1"
```

Il comando:

1. Restringe i permessi della sola cartella `C:\SCStudioBackup` e delle sottocartelle
   gestite a utente corrente, amministratori e SYSTEM. Non usare una cartella
   con contenuti estranei.
2. Verifica gli strumenti e genera `recovery\recovery.agekey` se non esiste.
   **Non mostra la chiave privata e non la sovrascrive.**
3. Chiede di custodire una copia separata della chiave. Salvare in modo sicuro
   l'intero file, per esempio in un gestore di password approvato o su un altro
   dispositivo protetto. Non basta conservarlo sullo stesso disco dei backup.
   Solo dopo la copia, digitare `CONFERMO` nel prompt.
4. Chiede i dati di connessione e cifra la password con DPAPI Windows in
   `config\database.credential.xml`. Il file non è utilizzabile da un altro utente
   o da un altro computer. La chiave age separata è invece ciò che permette di
   recuperare gli archivi anche dopo la perdita del PC.
5. Esporta **solo certificati pubblici** dalle autorità radice già attendibili
   per Windows in `config\roots.pem`, per autenticare il server TLS. Non esporta
   chiavi private dei certificati e non aggiunge autorità attendibili.
6. Salva configurazione e chiave pubblica e, se autorizzato, registra la sorgente
   `SCStudioBackup` nel registro eventi Applicazione.

Non fa login a Render e non crea un backup. Non sovrascrive una configurazione
già presente: per rotazione delle credenziali o delle chiavi serve un intervento
controllato, preservando le chiavi degli archivi precedenti. Se il primo tentativo
si interrompe dopo la generazione della chiave, la successiva inizializzazione
riutilizza la stessa chiave.

## 5. Primo backup manuale, soltanto dopo l'accesso autorizzato

```powershell
& "C:\SCStudioBackup\scripts\Backup.ps1"
```

La connessione richiede TLS `verify-full` e usa le radici attendibili esportate
dal sistema. Non ripiega su connessioni senza verifica: un errore di certificato
va diagnosticato, non aggirato disabilitando TLS. Non usa URL/password sulla
riga di comando; la password viene resa disponibile soltanto nell'ambiente del
processo `pg_dump`, poi rimossa dai riferimenti gestiti. L'accesso al PC da parte
di un attaccante con lo stesso account rimane una minaccia: DPAPI non lo elimina.

Il programma impone sessioni di sola lettura sul sorgente, crea un dump custom,
verifica che `pg_restore --list` lo legga, cifra con age e produce un checksum.
Ogni archivio completo è una cartella con tre file:

```text
archivi\giornalieri\sc-studio-DATA-IDENTIFICATIVO\
    backup.dump.age
    backup.dump.age.sha256
    manifest.json
```

La pubblicazione avviene spostando la cartella completata sullo stesso disco.
Un file cifrato parziale non viene presentato come backup valido. Esecuzioni
contemporanee vengono rifiutate. Servono almeno 1 GB libero; il controllo di
errore resta necessario anche se lo spazio iniziale è sufficiente.

Conservazione: giornalieri 14 giorni, copia della domenica 56 giorni,
copia del primo giorno del mese 12 mesi. Il calendario usa l'ora locale del PC;
i nomi e i metadati usano UTC. Verificare data, ora e fuso di Windows.
La pulizia avviene soltanto dopo un nuovo backup riuscito, su cartelle con nome,
manifest e checksum riconoscibili. File estranei, percorsi con junction/link
simbolici e archivi incoerenti non vengono eliminati automaticamente.

Il comando non ha una funzione di ripristino sul sorgente e non richiama
applicazione Flask, SMTP, scheduler applicativo o Google Calendar.

## 6. Controllo dell'esito

```powershell
& "C:\SCStudioBackup\scripts\Backup.ps1" -Check
```

Questo controllo non si collega al database: controlla l'ultimo esito, la presenza
dell'archivio, il checksum e l'età massima di 24 ore. Lo stato si trova anche in
`logs\status.json`; i log non contengono credenziali, output nativo o dati paziente.

Codici di uscita del backup: `0` completato, `1` errore, `2` archivio prodotto ma
problema di conservazione, `3` blocco di esecuzione non acquisito. Un esito non
zero non va ignorato. Dopo un errore la data dell'ultima copia riuscita resta
disponibile. Il checksum rileva alterazioni accidentali; age verifica anche
l'autenticità del contenuto durante la decifratura.

Gli eventi locali vengono scritti se la sorgente è disponibile. **Non sono
configurati avvisi email, notifiche push o un controllo remoto del PC spento nel pacchetto originale.**
L'eventuale monitoraggio va ancora configurato; vedere lo stato in Utilità di
pianificazione non sostituisce il controllo quotidiano dell'ultima copia valida.

## 7. Provare la chiave di recupero

Sostituire il nome d'esempio con la cartella reale del primo archivio:

```powershell
& "C:\SCStudioBackup\scripts\Verify-Archive.ps1" `
  -ArchiveDirectory "C:\SCStudioBackup\archivi\giornalieri\NOME_CARTELLA_REALE" `
  -IdentityPath "C:\SCStudioBackup\recovery\recovery.agekey"
```

Il comando verifica checksum, decifratura autenticata e struttura PostgreSQL,
poi elimina il dump temporaneo. Non modifica nessun database. Per provare anche
il recupero fuori dal PC utilizzare la copia separata della chiave, non soltanto
quella sul disco originale. Dopo aver verificato copie e recupero si può togliere
la chiave privata dal computer che genera i backup, custodendola altrove; i job
usano soltanto la chiave pubblica. Non eliminare mai l'ultima copia della chiave.

Questo non è ancora il collaudo di un restore completo. Prima del GO occorre
restaurare in un database isolato e controllare schema e contenuti, con qualunque
applicazione, email, scheduler e Calendar disattivati. Non ripristinare sopra
Render operativo. Il formato `.age` **non** si decifra con il vecchio script
`restore_postgres.sh` basato su OpenSSL: utilizzare age e la procedura dedicata.

## 8. Solo dopo il collaudo: pianificazione

Non viene installato nessun job automaticamente. In Utilità di pianificazione,
con lo stesso account della configurazione, l'azione futura sarà:

- Programma: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
- Argomenti: `-NoProfile -NonInteractive -File "C:\SCStudioBackup\scripts\Backup.ps1"`
- Cartella iniziale: `C:\SCStudioBackup\scripts`

Esecuzione giornaliera proposta alle 21:00, anche senza sessione aperta;
recuperare gli avvii saltati, riprovare ogni 15 minuti fino a tre volte, non
avviare istanze sovrapposte. Non scegliere il contesto S4U senza password se
impedisce accesso alla rete o alle credenziali. La password Windows si inserisce
nel pannello del PC, non nello script. Non richiedere privilegi elevati al job
se non necessari. Verificare un'esecuzione senza sessione interattiva prima di
considerare attivo il sistema. Il controllo `-Check` può essere pianificato
separatamente, ma nessun controllo eseguito soltanto sul PC rileva il guasto
mentre il PC stesso è spento.

## Evidenza tecnica e limiti

Il nucleo del pacchetto è stato eseguito con PowerShell 7.6.7 su macOS, age 1.3.2
e PostgreSQL 18 locale su solo socket Unix, con soli record sintetici: dump,
cifratura, decifratura, restore su database distinto, checksum alterato,
cifratura manomessa, errori degli strumenti, concorrenza, pulizia e retention.
La suite dedicata ha superato **42 asserzioni**, oltre al confronto delle righe
recuperate eseguito da SQLAlchemy. Nessun dato o backup Render è stato letto.

Non sono stati verificati nativamente su Windows 11/PowerShell 5.1: ACL NTFS,
DPAPI, esportazione delle autorità radice, eventi Windows, TLS verso Render e
Utilità di pianificazione. La sintassi dei quattro script è stata analizzata
con il parser PowerShell, ma il parser 7 non certifica da solo il runtime 5.1.
Il test reale sul PC resta necessario prima dell'attivazione.

Riferimenti: [age](https://github.com/FiloSottile/age),
[DPAPI ed Export-Clixml](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/export-clixml?view=powershell-5.1),
[TLS PostgreSQL](https://www.postgresql.org/docs/18/libpq-ssl.html).

## Avviso remoto opzionale dopo 72 ore — aggiornamento 22 ottobre

Lo stato corrente del collaudo Windows riportato dal committente è in
`docs/OPERATIONS.md`; la sezione precedente descrive il collaudo iniziale del
nucleo. Per lo stato di installazione e collaudo del monitor sul PC Windows
consultare quella fonte; le istruzioni seguenti restano la procedura riutilizzabile.

Su Healthchecks il controllo `Backup Windows` usa 71 ore di periodo più 1 ora
di tolleranza, email solo `down`, nessun report o reminder periodico. Non
condividere il Ping URL in chat o nel repository: consente di inviare segnali
per quel controllo. Non copiarvi il Ping URL del Mac.

Non sovrascrivere `Backup.ps1` o `StudioBackup.psm1`: conservare tutte le
correzioni locali. Il pacchetto aggiuntivo contiene soltanto tre nuovi file:
`Backup-Monitored.ps1`, `StudioMonitor.psm1` ed `Enable-Monitor.ps1`.
Il primo esegue il vecchio backup in un processo separato; solo con codice 0
e un `lastSuccessUtc` nuovo chiama il modulo monitor. Conserva sempre il codice
di uscita del backup. Errori del monitor non trasformano un backup riuscito in
un backup fallito. Non cambia le credenziali database né i vecchi script.

Trasferire il pacchetto al Windows, estrarlo in una cartella separata e
aggiungere i tre file a `C:\SCStudioBackup\scripts` solo se non esistono già.
Analizzare prima la sintassi con il parser PowerShell locale.
Eseguire `Enable-Monitor.ps1` con lo stesso account del backup e dell'attività: chiede
il solo Ping URL Windows con input nascosto e lo protegge tramite DPAPI in
`config/monitor.credential.xml`, nella cartella privata esistente. Non modifica
le credenziali del database o la pianificazione. Provare poi manualmente
`Backup-Monitored.ps1` e verificare il nuovo segnale effettivo sul servizio.
Solo dopo il test modificare l'azione dell'attività esistente sostituendo
`Backup.ps1` con `Backup-Monitored.ps1`; mantenere eseguibile, opzioni, account,
trigger e cartella di lavoro. Se il task è in esecuzione attendere il termine.
Non eliminare o ricreare l'attività. Il ripristino consiste nel rimettere
`Backup.ps1` nell'azione, senza cancellare gli archivi.

Dopo un nuovo backup con esito 0 viene inviato un POST HTTPS vuoto. Errori,
`-Check` e backup non completati non inviano segnali. Il timeout è 8 secondi,
i reindirizzamenti sono vietati e la verifica TLS di sistema resta attiva.
Non inviare log, contenuti di backup, password o dati identificativi.
Un errore di consegna viene registrato solo in `logs/monitor.json` e non
invalida il backup; non si reinviano vecchi successi spostando la scadenza.
Il controllo si arma soltanto al primo segnale effettivamente ricevuto:
`Never` non significa monitoraggio attivo. Verificare sul PC un nuovo backup,
`logs/monitor.json` e la ricezione in Healthchecks prima di dichiararlo attivo.
