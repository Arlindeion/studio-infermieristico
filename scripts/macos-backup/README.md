# Backup indipendente macOS

> Allineamento operativo del 22 ottobre 2026: stato del dominio, verifiche residue e prossimi sviluppi sono nella [roadmap corrente](../../docs/ROADMAP.md), D-131–D-132. Questo documento resta un riferimento tematico, non autorizza apertura pubblica, spesa o nuove attivazioni.

Procedura corrente: [OPERATIONS.md](../../docs/OPERATIONS.md#backup-e-ripristino-postgresql).
Non importa Flask, non avvia scheduler applicativi e non modifica Calendar.

## Installazione locale

Richiede FileVault attivo, Python 3.14, client PostgreSQL 18 e age. La cartella
privata non sincronizzata è `~/Library/Application Support/SCStudioBackup`.
Installare qui `backup.py` e `install.py` con permessi 600. Il comando
`install.py --prepare CHIAVE_PUBBLICA_AGE` prepara solo configurazione pubblica;
non sovrascrive configurazioni esistenti. Usare la stessa chiave pubblica
Windows, non copiare la chiave privata nella cartella operativa.

`install.py --credentials` chiede due volte la password PostgreSQL di
`studio_backup` in finestre locali nascoste. La salva nel Portachiavi sotto
`it.scstudioinfermieristico.backup.postgres`, account `studio_backup`;
non negli argomenti del processo, file di configurazione o log. Non sovrascrive
credenziali già presenti. Nessuna password va inviata in chat.

Eseguire prima `backup.py --preflight`, poi `backup.py` per un backup reale e
`backup.py --check` per il controllo locale senza connessione al database.
Soltanto dopo un backup riuscito `install.py --activate` installa il LaunchAgent.
Utilizzare un interprete Python assoluto con opzioni `-I -B`.

## Pianificazione e limiti

Alle 22:00 locali, all'accesso e ogni ora il job verifica se occorre una copia:
salta l'export se la scadenza giornaliera è già coperta da un archivio integro.
Recupera al risveglio; da spento non esegue nulla e riparte solo dopo l'accesso
dell'utente. Non è un servizio prima del login. `caffeinate` impedisce soltanto
lo stop inattivo durante il singolo tentativo, senza cambiare le impostazioni
energetiche. Il PC Windows normalmente acceso resta la destinazione primaria
per l'obiettivo di una copia ogni 24 ore.

Autorizzare su Render soltanto l'IP pubblico della macchina con `/32`.
Se cambia, la connessione può fallire: aggiornare la singola regola dopo
verifica, senza aprire `0.0.0.0/0`. TLS usa `verify-full`; l'utente è dedicato
alla lettura. Nessun ripristino sul database operativo.

## Archivi e controlli

Formato `pg-custom-age-v1`, compatibile con gli archivi Windows: dump custom
cifrato age, checksum e manifest. Il vecchio restore OpenSSL non legge `.age`.
Il dump temporaneo resta nella cartella privata `.work` e viene rimosso anche
su errori gestiti. Spegnimenti improvvisi possono lasciare temporanei: non
scambiarli per backup completati. FileVault protegge il disco.

Conservazione: giornalieri 14 giorni, domeniche 8 settimane, primi del mese
12 mesi. Le copie periodiche sono file indipendenti. La pulizia avviene solo
dopo un nuovo backup riuscito e solo sugli archivi propri validati, senza
cancellazioni ricorsive. Archivi corrotti o estranei non vengono eliminati.

Consultare `logs/status.json`: `state`, `stage`, `lastSuccessUtc`. Codici: 0
riuscito o esecuzione non dovuta, 1 errore, 2 avviso conservazione. `--check`
richiede una copia valida entro 24 ore. Il monitor remoto opzionale descritto
sotto non sostituisce il controllo quotidiano. `launchd` caricato non dimostra
un'esecuzione riuscita dopo stop o riavvio; serve un collaudo reale separato.

Per disattivare soltanto questo job, senza cancellare gli archivi:

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/it.scstudioinfermieristico.backup.plist"
```

Test sintetico isolato: `pytest tests/test_macos_backup.py`. Il test con client
reali richiede `STUDIO_MAC_TEST_PGHOST` verso un cluster temporaneo appositamente
preparato, mai verso Render. Non legge Portachiavi o chiavi private reali.

## Avviso remoto dopo 72 ore

Healthchecks: controllo indipendente `Backup Mac`, periodo 71 ore più 1 ora di
tolleranza (totale 72). Integrazione email solo `down`, senza report o reminder
periodici. `install.py --monitor` chiede localmente il Ping URL e lo conserva
nel Portachiavi dedicato, senza salvarlo nel repository. Non inviare URL in chat.

Il programma invia un POST HTTPS vuoto soltanto dopo un **nuovo** backup con
esito 0 e archivio verificato: mai per `--check`, `--preflight`, esecuzioni
saltate o errori. Nessun segnale `/start` o `/fail`, così gli errori singoli non
anticipano l'avviso. Nessun dato clinico, log o nome di file viene trasmesso.
Il fornitore vede inevitabilmente IP e orario della richiesta. Timeout 8 secondi,
TLS verificato e nessun reindirizzamento. Un errore del monitor non altera il
backup: viene registrato separatamente in `logs/monitor.json`, senza dettagli
sensibili. Non si ritrasmettono vecchi successi, per non spostare falsamente la
scadenza. Dopo un problema di consegna, il successivo nuovo backup riprova.

L'avviso si arma soltanto quando Healthchecks riceve il primo segnale reale;
`Never` non è un monitor attivo. Il monitor non sostituisce un restore.
