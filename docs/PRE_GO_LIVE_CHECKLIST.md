# Checklist unica di verifica prima del dominio pubblico

Questa checklist è un **gate operativo**, non un attestato di esito. È complementare a [ROADMAP.md](ROADMAP.md) e [OPERATIONS.md](OPERATIONS.md). Le verifiche su Render devono essere documentate da chi ha accesso al servizio; non inserire credenziali, dati identificativi o output contenenti dati sanitari nei report.

## 1. Codice e deployment

- [ ] Verificare commit attivo su Render e commit approvato su main; bloccare auto-sync durante il gate.
- [ ] Eseguire la suite `pytest`, test JavaScript e CI sulla revisione di rilascio (non basta il solo audit statico).
- [ ] Eseguire `DISABLE_SCHEDULER=true flask --app app db upgrade`, `db check` e `validate-config` nella finestra autorizzata.
- [ ] Eseguire `patient_cutover_preflight.py --allow-applied` in modalità prevista dalla procedura; interrompere se lo stato DB non corrisponde alle aspettative.
- [ ] Smoke test Pazienti 2.0: anagrafica, recapiti, collegamento pratiche, storico Calendar, autorizzazioni, audit, archivio e logout.
- [ ] Confermare `/healthz` e assenza di errori inattesi nei log, senza esportare dati personali.

## 2. Privacy, sicurezza e resilienza

- [ ] Verificare autenticazione e CSRF, inclusi i link di conferma arrivati via email.
- [ ] Verificare che nessuna pagina con token riservato sia memorizzata in cache o indicizzabile.
- [ ] Controllare i limiti delle richieste, gli header di sicurezza e il comportamento a sessione scaduta.
- [ ] Verificare dati sintetici e cancellarli **solo dopo riconciliazione** con i dati reali.
- [ ] Prima del primo dato reale: verificare che PITR sia effettivamente incluso e attivo sul piano Render, backup cifrati programmati, conservazione e ripristino su database separato.
- [ ] Registrare un piano di rollback che tenga conto delle migrazioni di schema e non sovrascriva dati nuovi.

## 3. Prenotazioni e integrazioni

- [ ] Richiesta prestazione: salvataggio, notifica, conferma, modifica, annullamento.
- [ ] Corso: iscrizione singola e di coppia, capienza, lista d'attesa, conferma con token.
- [ ] Sonno: prenotazione call, questionario privato, proposta, pagamento configurato o opzione non disponibile.
- [ ] Google Calendar: creazione/modifica/cancellazione e recovery senza duplicati.
- [ ] SMTP: mittente valido, recapito a destinatari controllati, fallimento senza perdita della pratica.
- [ ] Verificare IBAN e intestatario o nascondere metodi non ancora operativi.

## 4. Passaggio al dominio

- [ ] Approvazione esplicita GO/NO-GO.
- [ ] Configurare `APP_ENV=production`, `PUBLIC_BASE_URL=https://scstudioinfermieristico.it` e rimuovere le variabili di autenticazione staging solo nel cutover.
- [ ] Controllare record DNS apex e `www`, certificato HTTPS, redirect canonici, robots e sitemap.
- [ ] Verificare link nei messaggi, canonical, Open Graph, cookie/analytics e indicizzazione.
- [ ] Verificare SPF, DKIM e DMARC della casella effettivamente mittente.
- [ ] Monitorare errori applicativi, invii, Calendar e conversioni dopo la pubblicazione.

**Non eseguire su Render comandi distruttivi, reset database o cancellazioni automatiche senza validazione dei conteggi e approvazione.**
