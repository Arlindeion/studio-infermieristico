# Roadmap

Stato aggiornato al 29 luglio 2026. Il checkpoint interno è il 15 settembre 2026 e richiede sia un sito tecnicamente pronto e sicuro sia una prima campagna online/social coerente con la nuova identità. Non è una scadenza pubblica.

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
- Homepage ridisegnata come racconto a scene singole, con corsi e consulenza del sonno in due schermate distinte e priorità visiva ai corsi. I quattro corsi sono raccolti nelle famiglie `Sicurezza` e `Nascita e crescita`; quando non esistono date future non annullate la raccolta di interesse chiude la scena corsi e la scena Date scompare. La scena nascita usa una firma continua per i cinque professionisti; metodo e testimonianza formano un'unica sequenza. L'iscrizione OPI resta nei contenuti professionali dedicati e non viene trattata come beneficio commerciale.
- Regia scroll della homepage estesa a sette scene, oppure otto quando esistono date: ogni snap desktop occupa una sola schermata senza scroll interno; sotto 1024×640 px, su mobile e con movimento ridotto lo scorrimento resta libero. I laptop tra 640 e 840 px di altezza usano una composizione verticale più compatta. Il filo e la staffetta tipografica sono stati rimossi. Il sistema ibrido collega le prime tre scene con cuore e cistifellea scontornati; dalla scena sonno in poi i passaggi condividono scala, fuoco e un completamento legato al contenuto: fotografia del team, linea del metodo, feed attività e scelte finali. Su desktop ogni passaggio dura 0,85 secondi con arresto esatto sullo snap; gli impulsi del trackpad non possono saltare una scena. La guida laterale si adatta alle scene presenti e le raggruppa nei capitoli `Orientarsi`, `Conoscere` e `Scegliere`. Header reattivo e navigazione di scena restano attivi. Il parallax della hero usa livelli definitivi ricavati dall'originale `SELENE-16.jpg`, con fondale fotografico e maschera per-pixel di capelli e spalle.
- Pagine interne ricondotte allo stesso linguaggio visivo della homepage senza replicarne lo snap: contenuti e servizi mantengono scroll libero con ritmo editoriale e avanzamento di lettura, moduli e questionari usano una regia quieta, conferme ed esiti hanno una composizione dedicata. Chi sono, FAQ, directory corsi e privacy non usano più griglie di schede equivalenti; la CTA mobile si nasconde quando l'azione corrispondente è già visibile.
- Transizione orizzontale fra le pagine pubbliche implementata senza router client-side: la destinazione copre progressivamente la pagina corrente dietro il bordo rosso, il ritorno alla homepage procede in senso inverso e il fallback mantiene sempre i link funzionanti. Le ancore verso altre pagine aprono lo stesso punto sia nell'anteprima sia nel documento definitivo.
- Landing `call-first` sul sonno infantile 0-12 mesi, con gerarchia responsive, prezzi leggibili e call gratuita come azione dominante. Nello snap sonno della homepage `Scopri la consulenza` apre direttamente il confronto delle tre formule, mentre `Prima parliamone` apre il calendario della call.
- Prenotazione breve della call sonno con slot provvisorio, controllo incrociato database/Calendar, gestione admin ed email di conferma.
- Questionario sonno privato sul sito, inviabile solo dopo la call e la scelta della formula.
- Prestazioni infermieristiche mantenute in un flusso separato.
- Metadati condivisi, canonical, Open Graph e dati strutturati principali.
- Tracciamento differenziato delle CTA predisposto per GA4 e subordinato al consenso.
- Iscrizioni a corsi collegate alle date e modulo unico di ricontatto con scelta della tematica quando il calendario è vuoto.
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

1. **Definire policy e vincoli operativi — `In corso` (P0).** Durate, prezzi, rate, assistenza, cancellazioni, spostamenti, rimborsi e assenze della consulenza sonno sono stati approvati e registrati il 21 luglio 2026. Il 29 luglio è stato chiarito che Arzamed conserva sempre l'orario di fine effettivo e che le prestazioni non usano durate fisse: anche nell'admin del sito Selene sceglie la durata prima della conferma. Resta la validazione professionale del testo contrattuale/recesso. **Criterio di uscita:** decisioni validate e registrate nelle fonti competenti.
2. **Mettere in sicurezza la creazione dell'amministratore — `Completato` (P0).** Le credenziali automatiche sono state eliminate; locale e produzione usano un bootstrap esplicito, la password minima è di 16 caratteri e la produzione rifiuta sia configurazioni incomplete sia la credenziale legacy prevedibile. **Evidenza:** test dedicati e suite completa superati il 20 luglio 2026. **Criterio di uscita:** soddisfatto.
3. **Definire l'infrastruttura di staging e produzione — `Completato` (P0).** Dominio e posta sono protetti e collaudati. Render Francoforte ospiterà Web Service e PostgreSQL separati: piano gratuito per lo staging su `onrender.com`, Web Service Starter e PostgreSQL Basic-256mb nuovi e vuoti per la produzione; lo staging esistente non viene promosso. HTTPS è gestito, auto-deploy resta disattivato, i segreti vanno nel pannello e la prima accensione delle risorse definitive resta una preproduzione con Basic Auth e `noindex`. Il 29 luglio la scelta delle risorse separate è stata approvata e preparata in `render.production.yaml`, senza sincronizzazione né costi. **Criterio di uscita:** soddisfatto.
4. **Creare e verificare le migrazioni Alembic — `Completato` (P0).** La baseline `56dda7f5137f` crea tutte le tabelle, relazioni, unicità e indici; la revisione `9b7e2d4c6a10` aggiunge qualificazione, UTM e stato dei promemoria email della call sonno, `7f3c1a2d9e40` rimuove i campi WhatsApp non più utilizzati e `4d8b2c7a91e6` aggiunge la durata effettiva agli appuntamenti esistenti con valore iniziale di 30 minuti. L'avvio operativo usa `flask db upgrade` e non `db.create_all()`. **Evidenza:** SQL PostgreSQL revisionato, upgrade su database vuoto, adozione senza perdita e `flask db check` senza operazioni mancanti verificati. **Criterio di uscita:** soddisfatto.
5. **Definire backup e ripristino — `Completato` (P0).** La produzione userà PITR Render e dump giornalieri cifrati sul PC dell'attività, con conservazione 14 giornalieri, 8 settimanali e 12 mensili; checksum, destinazione vuota e restore mensile sono obbligatori. **Evidenza:** backup e ripristino completi verificati su PostgreSQL 18.4 con dati sintetici il 20 luglio 2026; 12 tabelle e revisione Alembic recuperate correttamente. **Criterio di uscita:** soddisfatto.
6. **Preparare la configurazione di produzione — `In corso` (P0).** Validazione fail-fast, HTTPS/proxy, PostgreSQL obbligatorio, matrice dei segreti, SMTP Zimbra, secret file Calendar e log senza indirizzi email sono predisposti e testati localmente. Il 29 luglio sono stati rimossi i fallback Gmail, resi obbligatori server/porta/TLS e casella Zimbra approvati, aggiunto `PUBLIC_BASE_URL` per canonical e link assoluti e introdotto l'opt-in separato per le integrazioni reali nella preproduzione privata. Dal pannello staging sono state rimosse la variabile WhatsApp non più usata e le credenziali bootstrap. `render.production.yaml` prepara risorse separate e sicure per default, ma non è stato applicato: restano da inserire e verificare i valori reali soltanto dopo il futuro ordine di spesa. **Criterio di uscita:** avvio corretto senza segreti nel repository e log privi di dati personali superflui.
7. **Pubblicare uno staging privato — `Completato` (P0).** Lo staging HTTPS su Render conserva Basic Auth, indicizzazione disabilitata e PostgreSQL collegato in Francoforte. Il 29 luglio è stato distribuito manualmente il commit verificato `8a4ad84` di `codex/snap-homepage`: migrazione, bootstrap dell'admin esistente e avvio Gunicorn sono riusciti. `/healthz` è stato escluso dal limite globale; 55 richieste consecutive e i monitor del deploy hanno risposto `200` senza nuovi `429`. Dopo il controllo sono state rimosse dal pannello le due variabili `ADMIN_BOOTSTRAP_*` e la variabile WhatsApp non più usata; il riavvio ha confermato nuovamente admin esistente, bootstrap riuscito e health check stabile. Root, `robots.txt` e `/healthz` restituiscono rispettivamente `401`, `200` e `200`, con `X-Robots-Tag` globale e `Disallow: /`. Il 30 luglio Blueprint e Web Service sono stati allineati a `main`, mantenendo Auto Sync e auto-deploy disattivati. L'approvazione della modifica ha avviato comunque un deploy del commit `e4fea38`: è stato annullato subito e il deploy live è rimasto `8a4ad84`, senza variazioni di piani, dominio o integrazioni. Il Blueprint è stato poi disconnesso per revocare il relativo Sync Hook: servizio e database sono rimasti intatti, nessun nuovo deploy è partito e `/healthz` ha risposto `200`. Nella stessa data l'attività ha confermato di non aver mai inserito dati reali nel database di staging. **Criterio di uscita:** soddisfatto.
8. **Configurare e collaudare email e Google Calendar — `Da fare` (P0).** Verificare mittente SMTP, lettura Calendar/Arzamed, account di servizio con permessi minimi e scrittura degli eventi. **Criterio di uscita:** prove reali riuscite e anomalie registrate in `RegistroEvento`.
9. **Collaudare il flusso delle prestazioni sanitarie — `In corso` (P0).** La richiesta pubblica mantiene un blocco provvisorio di 30 minuti; l'admin richiede la durata effettiva prima della conferma e la usa per conflitti, disponibilità, modifiche ed evento Calendar. Il 29 luglio controlli automatici e visuali a 1440×900 e 390×844 px hanno verificato scelta, limiti, sovrapposizioni, persistenza, migrazione, fine dell'evento e avvisi distinti quando falliscono email o Calendar; è stata inoltre corretta la card appuntamento mobile che una regola CSS rendeva invisibile. Il domicilio resta fuori dalla prenotazione diretta. Restano da ripetere in preproduzione richiesta, conferma manuale, modifica e annullamento con email e Calendar reali. **Criterio di uscita:** percorso completo superato e domicilio mantenuto fuori dalla prenotazione diretta.
10. **Collaudare corsi e lista di interesse — `Completato` (P0).** Il 29 luglio i test sintetici hanno verificato tutte le tipologie pubbliche, date e stati, iscrizione singola e di coppia, conteggio dei posti, capienza raggiunta, proposta della data successiva, riapertura dopo annullamento, ricontatto in assenza di date, rubrica, filtro admin e rifiuto delle richieste aziendali nel form individuale. È preservata la regola operativa per cui una coppia può essere accettata quando resta un solo posto; la data si chiude alle richieste successive. **Evidenza:** suite completa di 164 test Python, 18 test JavaScript e `git diff --check` superata. **Criterio di uscita:** soddisfatto.
11. **Collaudare il percorso nascita — `Completato` (P0).** Il 29 luglio i test sintetici hanno verificato pagina e richiesta open day, modulo completo accessibile soltanto tramite link privato e sempre `noindex`, edizioni aperte/chiuse, nove incontri, iscrizione della coppia come un posto, capienza e riapertura dopo annullamento, creazione e aggiornamento delle presenze, rubrica, conferme email simulate ed export PDF. Il controllo finale della capienza usa un blocco di riga su PostgreSQL per evitare due iscrizioni simultanee sull'ultimo posto. **Evidenza:** suite completa di 164 test Python, 18 test JavaScript e `git diff --check` superata. **Criterio di uscita:** soddisfatto.
12. **Collaudare il flusso della consulenza del sonno — `In corso` (P0).** Il 29 luglio i test sintetici hanno verificato prenotazione qualificata, disponibilità nazionale incluso il sabato, UTM, blocco provvisorio Calendar, promemoria email senza duplicati, conferma, modifica, annullamento, call conclusa, scelta della formula, invito e accesso al questionario privato `noindex`. Gli avvisi admin distinguono i fallimenti email da quelli Calendar. Restano le stesse prove con integrazioni reali e la definizione/collaudo del passaggio di pagamento. **Criterio di uscita:** flusso completo verificato con integrazioni reali e disponibilità nazionale invariata.
13. **Verificare la resilienza dei flussi — `In corso` (P0).** Il 29 luglio i test sintetici locali hanno confermato che errori SMTP non perdono prenotazioni, iscrizioni corso, iscrizioni e presenze del percorso nascita o call sonno; errori di scrittura Calendar non perdono conferme o call, mentre un errore di lettura Calendar usa la cache disponibile. Le anomalie vengono registrate in `RegistroEvento`, sono visibili con avvisi comprensibili nell'admin e non espongono l'URL iCal nei log. Conferme, modifiche e annullamenti di prestazioni e call non dichiarano più “comunicazione inviata” quando l'email fallisce. Resta il collaudo controllato della stessa matrice in preproduzione con le integrazioni reali. **Criterio di uscita:** prenotazioni e iscrizioni restano salvate, gli errori secondari sono registrati e l'admin riceve avvisi comprensibili.
14. **Validare privacy, cookie e trattamento dati — `In corso` (P0).** Il 29 luglio il contatto e la forma dell'indirizzo postale sono stati allineati ai dati operativi approvati. Il comportamento tecnico è coperto da test: prima dell'accettazione non viene richiesto lo script GA4; rifiuto e revoca negano Analytics/Ads, interrompono gli eventi di conversione e rimuovono soltanto i cookie Analytics. GA4 e Meta restano non configurati. Restano da verificare informative, basi giuridiche, responsabili esterni, consensi, conservazione, configurazione Analytics, questionario sonno, collegamenti esterni e dati sanitari con competenza professionale adeguata. **Criterio di uscita:** testi e comportamento approvati; GA4 e Meta non ricevono eventi prima del consenso.
15. **Finalizzare contenuti e autorizzazioni — `In corso` (P1).** Il placeholder pubblico della landing sonno è stato sostituito, le fotografie disponibili risultano autorizzate anche per social e ads e la qualifica `infermiera e consulente del sonno infantile` è verificata. Restano le fonti cliniche e le prime testimonianze reali. **Criterio di uscita:** nessun contenuto pubblico privo di autorizzazione o ancora provvisorio.
16. **Eseguire il collaudo visuale, accessibilità e SEO — `In corso` (P1).** Il 21 luglio 2026 sono stati corretti gerarchie dei titoli, dimensioni intrinseche delle immagini, CTA concorrenti, widget WhatsApp globale, target touch admin e azioni mutative admin via POST. Il 29 luglio tutte le route pubbliche, i quattro dettagli corso, i moduli, le conferme, l'errore 404 e l'admin sintetico sono stati controllati localmente a 1440×900 e 390×844 px: nessun overflow, immagine locale mancante o campo pubblico visibile senza etichetta; apertura/chiusura del menu mobile e target dei controlli admin superati. Sono stati aggiunti il layout 404, `h1` e `noindex` mancanti nelle conferme e associazioni esplicite tra label e controlli nei moduli admin. Il controllo successivo della durata effettiva ha corretto anche la card appuntamento mobile nascosta per precedenza CSS. Canonical, Open Graph, `MedicalBusiness`, `Service` e link assoluti possono ora essere vincolati all'origine pubblica esplicita, indipendentemente dall'host Render. **Evidenza:** 164 test Python, 18 test JavaScript e `git diff --check` superati. Restano il controllo degli stati popolati con integrazioni reali e la verifica sul dominio definitivo. **Criterio di uscita:** controlli documentati, difetti bloccanti risolti, `pytest` e `git diff --check` superati.
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
- Valutare l'eventuale offerta di supporto dopo la nascita prima di ripristinare una pagina pubblica dedicata; la bozza attuale resta fuori da route, navigazione e indicizzazione.

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
