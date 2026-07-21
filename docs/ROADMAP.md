# Roadmap

Stato aggiornato al 21 luglio 2026. Il checkpoint interno è il 15 settembre 2026 e richiede sia un sito tecnicamente pronto e sicuro sia una prima campagna online/social coerente con la nuova identità. Non è una scadenza pubblica.

## Gate interno del 15 settembre

Il checkpoint è superato soltanto quando sono veri entrambi i risultati:

1. le attività P0 di sicurezza, dati, produzione e collaudo sono concluse;
2. la campagna iniziale sulla consulenza del sonno è pronta, misurabile e sostenuta da landing, contenuti social e processo di gestione dei contatti coerenti.

La sola finalizzazione grafica non basta. Se un requisito P0 resta aperto, il sito non è pronto all'esposizione pubblica anche se la campagna è stata preparata.

## Criterio di priorità

- `P0`: necessario prima dell'esposizione pubblica.
- `P1`: importante per un lancio credibile, rinviabile solo consapevolmente.
- `P2`: evoluzione successiva alla validazione.

## Completato o già implementato

- Identità principale definita: salvia dello studio, tipografia, linea rossa e fotografia reale.
- Header salvia responsive con testo scuro, gerarchia corsi/sonno verificata e footer verde profondo.
- Homepage riorganizzata intorno a corsi e consulenza del sonno, con schede editoriali differenziate, priorità visiva ai corsi, sezione nascita separata dall'header, calendario accessibile e stato vuoto orientato al ricontatto.
- Landing `call-first` sul sonno infantile 0-12 mesi, con gerarchia responsive, prezzi leggibili e call gratuita come azione dominante.
- Prenotazione breve della call sonno con slot provvisorio, controllo incrociato database/Calendar, gestione admin ed email di conferma.
- Questionario sonno privato sul sito, inviabile solo dopo la call e la scelta della formula.
- Prestazioni infermieristiche mantenute in un flusso separato.
- Metadati condivisi, canonical, Open Graph e dati strutturati principali.
- Tracciamento differenziato delle CTA predisposto per GA4 e subordinato al consenso.
- Iscrizioni a corsi collegate alle date e raccolta interesse quando manca una data.
- Gestione in admin di tipologie, capienza e stati dei corsi.
- Flusso privato del percorso nascita con edizioni, incontri, iscritti, presenze ed export PDF.
- Lettura degli impegni Google Calendar e scrittura degli eventi associati.
- Registro operativo per errori parziali di email e sincronizzazioni.
- Configurazione SQLite locale e PostgreSQL-ready.
- Creazione dell'amministratore messa in sicurezza: nessuna credenziale predefinita, bootstrap esplicito e arresto della produzione in presenza di configurazione mancante o credenziale legacy prevedibile; test dedicati superati.
- Prima riorganizzazione della documentazione in `docs/`.

Le funzionalità già presenti devono comunque superare il collaudo pre-lancio: “implementato” non equivale automaticamente a “pronto per produzione”.

## Piano operativo numerato verso il lancio

Questa è la checklist operativa canonica del progetto. I numeri degli step non vanno riordinati o riutilizzati: negli aggiornamenti si modifica lo stato e si aggiungono note o evidenze. Stati ammessi: `Da fare`, `In corso`, `Completato`, `Bloccato`. Uno step è `Completato` soltanto quando è soddisfatto il relativo criterio di uscita.

1. **Definire policy e vincoli operativi — `In corso` (P0).** Durate, prezzi, rate, assistenza, cancellazioni, spostamenti, rimborsi e assenze della consulenza sonno sono stati approvati e registrati il 21 luglio 2026. Restano la validazione del testo contrattuale/recesso e l'allineamento degli slot delle prestazioni con Arzamed. **Criterio di uscita:** decisioni validate e registrate nelle fonti competenti.
2. **Mettere in sicurezza la creazione dell'amministratore — `Completato` (P0).** Le credenziali automatiche sono state eliminate; locale e produzione usano un bootstrap esplicito, la password minima è di 16 caratteri e la produzione rifiuta sia configurazioni incomplete sia la credenziale legacy prevedibile. **Evidenza:** test dedicati e suite completa superati il 20 luglio 2026. **Criterio di uscita:** soddisfatto.
3. **Definire l'infrastruttura di staging e produzione — `Completato` (P0).** Dominio e posta sono protetti e collaudati. Render Francoforte ospiterà Web Service e PostgreSQL: piano gratuito per lo staging su `onrender.com`, poi almeno Starter e Basic-256mb per la produzione; HTTPS gestito, auto-deploy disattivato, segreti nel pannello e staging protetto con Basic Auth e `noindex`. **Evidenza:** configurazione documentata e avvio Gunicorn locale verificato il 20 luglio 2026. **Criterio di uscita:** soddisfatto.
4. **Creare e verificare le migrazioni Alembic — `Completato` (P0).** La baseline `56dda7f5137f` crea tutte le tabelle, relazioni, unicità e indici; la revisione `9b7e2d4c6a10` aggiunge qualificazione, consensi, UTM e stato dei promemoria della call sonno. L'avvio operativo usa `flask db upgrade` e non `db.create_all()`. **Evidenza:** SQL PostgreSQL revisionato, upgrade su database vuoto, adozione senza perdita e `flask db check` senza operazioni mancanti verificati. **Criterio di uscita:** soddisfatto.
5. **Definire backup e ripristino — `Completato` (P0).** La produzione userà PITR Render e dump giornalieri cifrati sul PC dell'attività, con conservazione 14 giornalieri, 8 settimanali e 12 mensili; checksum, destinazione vuota e restore mensile sono obbligatori. **Evidenza:** backup e ripristino completi verificati su PostgreSQL 18.4 con dati sintetici il 20 luglio 2026; 12 tabelle e revisione Alembic recuperate correttamente. **Criterio di uscita:** soddisfatto.
6. **Preparare la configurazione di produzione — `In corso` (P0).** Validazione fail-fast, HTTPS/proxy, PostgreSQL obbligatorio, matrice dei segreti, SMTP Zimbra, secret file Calendar e log senza indirizzi email sono predisposti e testati localmente. Restano da inserire i valori reali nel pannello Render durante la creazione dello staging e, più avanti, nell'ambiente produzione. **Criterio di uscita:** avvio corretto senza segreti nel repository e log privi di dati personali superflui.
7. **Pubblicare uno staging privato — `Completato` (P0).** Staging HTTPS pubblicato su Render con Basic Auth, indicizzazione disabilitata e PostgreSQL collegato. Accesso al sito e all'area amministrativa verificati il 20 luglio 2026; correzione del nome del logo per Linux distribuita con commit `c99ae81`. **Criterio di uscita:** soddisfatto.
8. **Configurare e collaudare email e Google Calendar — `Da fare` (P0).** Verificare mittente SMTP, lettura Calendar/Arzamed, account di servizio con permessi minimi e scrittura degli eventi. **Criterio di uscita:** prove reali riuscite e anomalie registrate in `RegistroEvento`.
9. **Collaudare il flusso delle prestazioni sanitarie — `Da fare` (P0).** Provare richiesta, conferma manuale, modifica, annullamento, email, Calendar e gestione degli appuntamenti domiciliari. **Criterio di uscita:** percorso completo superato e domicilio mantenuto fuori dalla prenotazione diretta.
10. **Collaudare corsi e lista di interesse — `Da fare` (P0).** Provare ogni tipologia, capienza, coppia, corso pieno, assenza di date, ricontatto e aziende/gruppi. **Criterio di uscita:** conteggi e stati corretti; aziende e gruppi restano nel contatto diretto.
11. **Collaudare il percorso nascita — `Da fare` (P0).** Provare open day, modulo privato non indicizzato, edizioni, incontri, iscritti, presenze e conteggio posti. **Criterio di uscita:** flusso pubblico e privato verificato senza esposizione del modulo completo.
12. **Collaudare il flusso della consulenza del sonno — `In corso` (P0).** Prenotazione qualificata, disponibilità del sabato, consensi separati, UTM e promemoria email/WhatsApp sono predisposti. Restano le prove reali di Calendar, template WhatsApp, conferma, modifica, annullamento, call conclusa, pagamento e questionario privato. **Criterio di uscita:** flusso completo verificato con integrazioni reali e disponibilità nazionale invariata.
13. **Verificare la resilienza dei flussi — `Da fare` (P0).** Simulare separatamente indisponibilità e errori di email e Calendar. **Criterio di uscita:** prenotazioni e iscrizioni restano salvate, gli errori secondari sono registrati e l'admin riceve avvisi comprensibili.
14. **Validare privacy, cookie e trattamento dati — `Da fare` (P0).** Verificare informative, consensi, conservazione, Analytics, questionario sonno, WhatsApp Business Platform e dati sanitari con competenza professionale adeguata. **Criterio di uscita:** testi e comportamento approvati; GA4 e Meta non ricevono eventi prima del consenso.
15. **Finalizzare contenuti e autorizzazioni — `In corso` (P1).** Il placeholder pubblico della landing sonno è stato sostituito e le fotografie disponibili risultano autorizzate anche per social e ads. Restano la verifica del claim `consulente certificata`, le fonti cliniche e le prime testimonianze reali. **Criterio di uscita:** nessun contenuto pubblico privo di autorizzazione o ancora provvisorio.
16. **Eseguire il collaudo visuale, accessibilità e SEO — `In corso` (P1).** Il 21 luglio 2026 sono stati corretti gerarchie dei titoli, dimensioni intrinseche delle immagini, CTA concorrenti, widget WhatsApp globale, target touch admin e azioni mutative admin via POST. Restano il controllo completo di tutte le pagine a 1440 px e 390 px, menu, form, admin, stati vuoti, contrasto, tastiera, focus, label, overflow, metadati, canonical, Open Graph e dati strutturati. **Criterio di uscita:** controlli documentati, difetti bloccanti risolti, `pytest` e `git diff --check` superati.
17. **Preparare processo e misurazione commerciale — `In corso` (P1).** Tre formule, capacità, prezzi, KPI, limite settimanale delle call e tracciamento UTM sono definiti. Restano pagamento, stato cliente, misurazione Meta/GA4 con consenso e verifica del tempo dopo i primi cinque percorsi. **Criterio di uscita:** processo da richiesta a cliente pagante misurabile e sostenibile.
18. **Preparare la campagna iniziale — `In corso` (P1).** Test nazionale Meta/Instagram, budget 200 € con checkpoint a 100 €, due angoli iniziali, presenza di Selene e assenza di testimonianze simulate sono approvati. Restano riprese, montaggio, copertine, configurazione tecnica e approvazione finale. **Criterio di uscita:** materiali approvati, CTA coerente e budget attivabile solo dopo la verifica del tracciamento.
19. **Eseguire il controllo finale pre-lancio — `Da fare` (P0).** Riesaminare sicurezza, migrazioni, backup, privacy, flussi, contenuti, misurazione e capacità operativa usando i criteri di uscita del progetto. **Criterio di uscita:** nessun P0 aperto o bloccato e decisione esplicita di procedere.
20. **Aprire il dominio pubblico e monitorare — `Da fare` (P0).** Collegare il dominio definitivo, verificare HTTPS, cookie, redirect, indicizzazione, invii reali, Calendar, log e conversioni; attivare la campagna solo dopo la stabilità iniziale. **Criterio di uscita:** sito pubblico stabile, monitorato e pronto a ricevere richieste qualificate.

## Dopo il lancio

### P2 — validazione e ottimizzazione

- Misurare richieste qualificate, provenienza, tasso call/percorso e carico di lavoro.
- Verificare mensilmente l'obiettivo interno di almeno tre testimonianze reali e autorizzate sulla consulenza del sonno, senza trasformarlo in un obbligo per le famiglie.
- Rivedere creatività, geografia e messaggi durante i tre mesi senza modificare contemporaneamente tutte le variabili.
- Rivedere prezzi e formato della consulenza sulla base dei dati reali.
- Costruire una mailing list con consenso e segmentazione minima.
- Migliorare il processo di ricontatto e il calendario editoriale.
- Creare landing verticali soltanto per campagne con obiettivo, pubblico e CTA definiti.

### P2 — gestionale commerciale

- Dashboard admin con viste oggi/settimana/mese e sezioni separate.
- Gestione dedicata di consulenze, aziende e ricontatti.
- Modelli corso duplicabili.
- Email automatica opzionale quando cambia un corso con iscritti.
- Export PDF generalizzato degli iscritti e partecipanti.
- Quiz guidato `Da dove parto?`.

### P2 — pagamenti

- Prenotazione dedicata della consulenza dopo la call gratuita.
- Pagamento online per consulenze e corsi selezionati.
- Eventuale rateizzazione.

Non introdurre pagamenti prima che policy, stati, email, capienza e calendario siano stabili.

## Criteri di uscita per il lancio

Il sito può essere considerato pronto quando:

- non usa credenziali prevedibili in produzione;
- i flussi principali salvano sempre i dati e comunicano correttamente lo stato;
- testi, immagini e testimonianze sono autorizzati;
- homepage, corsi, sonno e prestazioni hanno gerarchie distinte;
- test automatici e controlli visuali sono superati;
- analytics e cookie rispettano il consenso;
- ciò che non è automatizzato rimanda in modo chiaro a telefono o WhatsApp;
- Selene è pronta a gestire manualmente il volume di richieste generato;
- la campagna iniziale dispone di creatività coordinate, percorso di conversione verificato e misurazione coerente con il consenso.

## Aggiornamento della roadmap

Quando un'attività viene conclusa, spostarla nella sezione completata indicando se è stata anche collaudata. Se una scelta cambia l'ambito o la priorità del progetto, registrarla prima in `DECISIONS.md`.
