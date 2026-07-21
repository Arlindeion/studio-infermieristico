# Registro delle decisioni

Le decisioni precedenti sono registrate retrospettivamente nel luglio 2026 perché inizialmente vivevano nelle conversazioni e in `AGENTS.md`.

## D-001 — Crescita controllata

- Stato: approvata.
- Decisione: privilegiare valore percepito, qualità dei contatti e sostenibilità personale rispetto al volume.
- Motivo: capacità di investimento contenuta e obiettivo di work/life balance.
- Conseguenza: test manuali e piccoli prima di automazioni, pagamenti o campagne estese.

## D-002 — Due pilastri commerciali

- Stato: approvata.
- Decisione: corsi in presenza e consulenza del sonno sono i due pilastri visibili; le prestazioni infermieristiche restano prenotabili ma secondarie nella gerarchia promozionale.
- Motivo: i corsi sono validati e il sonno consente l'espansione nazionale.

## D-003 — Landing verticale sul sonno

- Stato: approvata.
- Decisione: `/consulenze-online` tratta il sonno infantile 0-12 mesi e non mescola ciuccio, spannolinamento e routine generiche.
- Motivo: una pagina verticale è più chiara per il traffico freddo e permette di validare un servizio alla volta.

## D-004 — Due formule per il sonno

- Stato: sostituita da D-033.
- Decisione: consulenza mirata da 75 € per un solo problema circoscritto; percorso personalizzato da 180 € come offerta principale quando più fattori si influenzano.
- Motivo: offrire una soglia d'ingresso senza svalutare il percorso completo.
- Da verificare: domanda nazionale, appropriatezza e disponibilità a pagare.

## D-005 — Call gratuita prima del pagamento

- Stato: approvata.
- Decisione: call conoscitiva gratuita di circa 20 minuti prima di proporre o far pagare una consulenza.
- Motivo: qualificare il contatto ed evitare servizi non appropriati.

## D-006 — Gerarchia della homepage

- Stato: approvata.
- Decisione: una promessa nel hero, massimo due CTA e sequenza definita in `SITE_MAP_AND_FLOWS.md`.
- Motivo: evitare l'effetto catalogo e rendere leggibile la priorità commerciale.

## D-007 — Palette salvia dello studio

- Stato: approvata.
- Decisione: usare `#B1BBA5` come salvia identitario, con il sistema cromatico documentato in `BRAND_SYSTEM.md`.
- Motivo: è il colore reale dello studio e offre maggiore riconoscibilità rispetto a verdi più scuri o sanitari.

## D-008 — Testo scuro nell'header

- Stato: approvata.
- Decisione: header salvia con navigazione e logo scuri, non bianchi.
- Motivo: il contrasto del bianco sul salvia è insufficiente; il verde scuro è più leggibile e coerente.

## D-009 — Fotografia reale come elemento distintivo

- Stato: approvata.
- Decisione: mantenere Selene e le attività reali come centro dell'identità; evitare stock generici e illustrazioni casuali.
- Motivo: credibilità sanitaria, fiducia e riconoscibilità personale.

## D-010 — Titolo breve della homepage

- Stato: approvata.
- Decisione: usare `S.C. Studio Infermieristico` nel titolo della scheda browser della homepage.
- Motivo: è identitario e resta leggibile nello spazio ridotto della scheda.

## D-011 — Prezzi non dominanti sul sito

- Stato: approvata.
- Decisione: comunicare prima valore e appropriatezza; mostrare i prezzi soprattutto nei materiali destinati a famiglie già interessate.
- Motivo: l'obiettivo iniziale è generare contatti qualificati, non competere sul prezzo.

## D-012 — Flussi separati

- Stato: approvata.
- Decisione: mantenere distinti prenotazione sanitaria, iscrizione corsi, percorso nascita, consulenza sonno e aziende/gruppi.
- Motivo: ogni flusso ha stati, capienza, informazioni e conferme differenti.

## D-013 — Settembre come obiettivo flessibile

- Stato: sostituita da D-025.
- Decisione: puntare all'inizio di settembre 2026 senza trattarlo come scadenza pubblica rigida.
- Motivo: permettere un lancio grafico coerente anche se alcuni automatismi inizialmente rimandano al contatto diretto.

## D-014 — Architettura tecnica conservativa

- Stato: approvata.
- Decisione: mantenere Flask/Jinja server-side, JavaScript vanilla e SQLAlchemy PostgreSQL-ready senza framework frontend o dipendenze non necessarie.
- Motivo: semplicità operativa e manutenzione sostenibile.

## D-015 — Feed Instagram nella homepage

- Data: 2026-07-15.
- Stato: approvata.
- Decisione: mantenere il feed Instagram come prova secondaria delle attività reali, dopo metodo e testimonianze e prima delle prestazioni e della CTA finale.
- Motivo: mostrare continuità, corsi e vita reale dello studio senza competere con i percorsi commerciali principali.
- Conseguenze: il collegamento diretto al profilo resta visibile anche se il feed esterno non viene caricato; Behold resta documentato nella privacy e autorizzato dalla Content Security Policy.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/privacy.html`.

## D-016 — Gradienti e ombre come strumenti visivi

- Data: 2026-07-15.
- Stato: approvata.
- Decisione: gradienti e ombre sono ammessi quando sostengono gerarchia, profondità o leggibilità e restano coerenti con palette e componenti esistenti.
- Motivo: un divieto generale non rispecchiava più il linguaggio visivo effettivo della homepage e delle pagine commerciali.
- Conseguenze: la manutenzione CSS elimina effetti soltanto insieme a componenti non più usati; nuovi effetti vanno comunque verificati rispetto ai token e agli stili equivalenti già presenti.
- Collegamenti: `AGENTS.md`, `BRAND_SYSTEM.md`, `static/css/`.

## D-017 — CSS modulare per responsabilità

- Data: 2026-07-15.
- Stato: approvata.
- Decisione: sostituire il foglio monolitico con moduli distinti per token, fondamenta, componenti condivisi, homepage, consulenza del sonno e amministrazione.
- Motivo: rendere esplicito l'ambito di ogni regola e ridurre il rischio di sovrapposizioni durante le modifiche future.
- Conseguenze: `base.html` carica sempre token, base e componenti; i moduli della homepage, della consulenza e dell'amministrazione vengono caricati soltanto dagli endpoint pertinenti. Gli adattamenti responsive restano vicini al relativo ambito e non si aggiungono sezioni versionate in coda ai file.
- Collegamenti: `AGENTS.md`, `BRAND_SYSTEM.md`, `templates/base.html`, `static/css/`.

## D-018 — Trasparenze centralizzate nei token

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: mantenere ogni colore `rgba()` in `tokens.css` e richiamarlo negli altri moduli tramite variabili con convenzione `--famiglia-aXX`.
- Motivo: evitare varianti alpha duplicate o quasi identiche disperse tra componenti, gradienti e ombre.
- Conseguenze: i moduli applicativi non contengono valori `rgba()` letterali; un test automatico impedisce di reintrodurli e verifica che ogni token alpha utilizzato sia definito.
- Collegamenti: `AGENTS.md`, `BRAND_SYSTEM.md`, `static/css/tokens.css`, `tests/test_app.py`.

## D-019 — Header orientato ai due percorsi principali

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: mantenere l'header salvia con naming e navigazione scuri e rendere immediatamente distinguibili `Corsi` come percorso prioritario in studio e `Consulenza sonno` come percorso online 0–12 mesi. Il simbolo anatomico usa il tratto bianco solo dentro un campo verde profondo compatto, mai direttamente sul salvia. `Corsi` usa un piccolo pannello funzionale verde azione con testo bianco, mentre il sonno resta su salvia chiaro con testo scuro. La casetta con il cuore mantiene l'accesso esplicito alla homepage. La linea rossa funziona come indicatore della sezione attiva e dell'elemento esplorato; su mobile i due percorsi aprono il pannello di navigazione prima dei collegamenti secondari.
- Motivo: rendere la gerarchia commerciale leggibile senza trasformare la navigazione in un catalogo e usare la firma del filo rosso come feedback funzionale, non ornamentale.
- Conseguenze: l'header è condiviso da tutte le pagine pubbliche, le prestazioni restano visibili ma secondarie e il menu corsi raccoglie i soli accessi principali senza modificare i flussi di iscrizione. Apertura, chiusura, focus, tastiera e movimento ridotto sono gestiti in `menu-mobile.js`.
- Collegamenti: `BRAND_SYSTEM.md`, `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/base.html`, `static/css/base.css`, `static/js/menu-mobile.js`.

## D-020 — Prenotazione e qualificazione della call sonno

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: la landing sonno porta a una prenotazione breve dedicata. La call dura circa 20 minuti, mentre lo slot tecnico di 30 minuti include 10 minuti finali di margine e viene salvato e bloccato subito come `In attesa` anche su Google Calendar. Diventa confermato soltanto con l'email di Selene entro il giorno lavorativo successivo. Un eventuale nuovo orario viene concordato prima al telefono e salvato come già accettato. Il questionario approfondito resta sul sito, privato e accessibile tramite token soltanto dopo la call e la scelta della formula.
- Motivo: ridurre l'attrito prima del primo contatto, evitare sovrapposizioni con Arzamed e raccogliere dati approfonditi solo quando servono realmente.
- Conseguenze: `/prenota-call-sonno` non condivide modello o stati con le prestazioni sanitarie; WhatsApp è secondario per gli indecisi; non esiste una proposta di modifica in attesa di accettazione; il salvataggio principale precede email e Calendar.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `CONTENT_AND_ASSETS.md`, `app.py`.

## D-021 — Landing sonno editoriale e compatta

- Data: 2026-07-16.
- Stato: approvata, aggiornata da D-033 per la presentazione delle formule.
- Decisione: organizzare `/consulenze-online` come landing `call-first`: difficoltà riconoscibili, accesso immediato al calendario, metodo essenziale, domande e CTA finale. La presentazione originaria di due formule soltanto nominate è sostituita da D-033, che rende confrontabili tre formule e relativi prezzi senza chiedere alla famiglia di scegliere prima del contatto. Mantenere la fotografia reale di Selene nella hero e riservare un secondo spazio fotografico dentro la sezione sul metodo.
- Motivo: rendere la pagina più fresca, leggibile e mirata, riducendo ripetizioni e carico cognitivo senza adottare codici visivi estranei all'identità sanitaria.
- Conseguenze: la CTA `Scegli l’orario della call` compare nella hero, subito dopo il riconoscimento del problema e alla fine. Nel blocco centrale l'azione occupa più spazio della rassicurazione sulle formule e non compete con un secondo collegamento WhatsApp. Le FAQ usano una composizione editoriale compatta a due colonne su desktop e controlli `details` chiaramente interattivi; su mobile pannello 0–12, fotografie e spaziature vengono ridotti per anticipare la call. Le tre formule sono presentate dopo il primo passaggio call-first con una gerarchia editoriale, non come card equivalenti. La seconda immagine usa `consulenza-sonno-neonato.jpg`, con proporzioni e testo alternativo definitivi; le fotografie selezionate risultano autorizzate anche per social e inserzioni. Bricolage Grotesque, Atkinson Hyperlegible, palette salvia e linea rossa restano gli elementi distintivi.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `templates/consulenze_online.html`, `static/css/consulenza.css`.

## D-022 — Ritagli morbidi per le fotografie della homepage

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: alleggerire le fotografie principali della homepage con sagome asimmetriche a bordi morbidi, ispirate a ritagli manuali. La hero usa un secondo livello salvia leggermente sfalsato; le immagini dei due pilastri usano forme alternate e più contenute.
- Motivo: valorizzare la fotografia reale e dare ritmo alla pagina senza ripetere l'arco della landing sonno o introdurre decorazioni estranee al brand.
- Conseguenze: le forme non devono coprire volti, mani o manufatti significativi; non vengono applicate automaticamente a calendari, feed esterni o immagini puramente funzionali. La linea rossa conserva un ruolo funzionale e non accompagna ogni ritaglio.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `static/css/homepage.css`.

## D-023 — Homepage orientata ai corsi con percorsi leggibili

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: mantenere corsi e consulenza del sonno come due accessi principali, rendendo i corsi visivamente prioritari con azione piena e collocando date e percorso nascita prima delle prove secondarie. Quando non esistono date, il calendario viene sostituito da uno stato vuoto compatto che raccoglie l'interesse; quando le date esistono, si apre sul primo mese utile. Prestazioni infermieristiche restano in una fascia separata e secondaria.
- Motivo: evitare che una card colorata o un calendario vuoto contraddicano la gerarchia commerciale e ridurre la lunghezza senza eliminare metodo e testimonianze autorizzate.
- Conseguenze: le CTA dirette alla call usano il nome coerente `Scegli l’orario della call`; link, date e controlli del calendario rispettano tastiera e target touch; il widget Instagram mantiene il proprio rendering nativo e il collegamento diretto al profilo resta sempre visibile; su mobile la fiducia iniziale usa una griglia 2×2.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/calendario.js`.

## D-024 — Sistema editoriale delle schede in homepage

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: estendere alla homepage il linguaggio contemporaneo dell'header attraverso schede asimmetriche, tab funzionali, superfici carta e salvia chiaro, ombre contenute e fotografie reali con ritagli morbidi. Le schede non devono essere tutte equivalenti: corsi resta il pannello più ampio e con CTA piena, sonno mantiene un trattamento secondario, prestazioni resta una fascia compatta.
- Motivo: aumentare riconoscibilità, profondità e qualità percepita senza trasformare la homepage in un catalogo di componenti ripetuti.
- Conseguenze: il corso di accompagnamento alla nascita usa una grande scheda verde chiaro separata dall'header salvia e un pannello carta autonomo per i cinque professionisti; metodo e testimonianze distinguono sequenza e prova sociale; calendario, Instagram e CTA finali condividono geometrie e bordi senza manipolare il rendering interno dei servizi esterni. La linea rossa segnala priorità o relazione soltanto nei punti funzionali.
- Collegamenti: `BRAND_SYSTEM.md`, `SITE_MAP_AND_FLOWS.md`, `templates/homepage.html`, `static/css/homepage.css`.

## D-025 — Gate interno del 15 settembre

- Data: 2026-07-16.
- Stato: approvata.
- Decisione: considerare riuscito il lancio al 15 settembre 2026 soltanto in presenza di due risultati congiunti: sito tecnicamente pronto e sicuro e prima campagna pubblicitaria online/social pronta a partire con la nuova identità grafica.
- Motivo: collegare il lavoro di prodotto alla capacità reale di iniziare l'acquisizione, senza ridurre il lancio a un restyling.
- Conseguenze: il 15 settembre è un checkpoint interno, non una scadenza pubblica; sicurezza, privacy, affidabilità dei dati e collaudo dei flussi restano condizioni non rinviabili; `ROADMAP.md` separa i criteri tecnici e commerciali del gate.
- Collegamenti: `PROJECT_BRIEF.md`, `ROADMAP.md`, `OPERATIONS.md`.

## D-026 — Test di tre mesi per la consulenza del sonno

- Data: 2026-07-16.
- Stato: approvata per la fase di validazione.
- Decisione: promuovere per tre mesi la consulenza del sonno 0-12 mesi attraverso annunci e contenuti social che portano alla scelta diretta dello slot. Il servizio resta nazionale; Abruzzo e regioni confinanti possono essere un limite tattico iniziale della distribuzione pubblicitaria soltanto per controllare la spesa. WhatsApp resta secondario per chi è indeciso.
- Motivo: raccogliere evidenze sull'intera fascia coperta dalla formazione di Selene, ridurre l'attrito tra annuncio e call e costruire prove specifiche per un servizio che non dispone ancora di testimonianze proprie.
- Conseguenze: l'obiettivo interno è arrivare ad almeno tre testimonianze reali, autorizzate e pubblicabili al mese sulla consulenza del sonno; non si promettono risultati e non si usano testimonianze di altri servizi. Il funnel misura almeno slot prenotato, call confermata, call svolta, formula scelta e consenso alla testimonianza. Budget, costo massimo per contatto e tono creativo/video restano da definire sui dati del test.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `locandine.md`.

## D-027 — Dominio operativo indipendente dalla trattativa

- Data: 2026-07-20.
- Stato: approvata.
- Decisione: registrare `scstudioinfermieristico.it` come dominio controllato direttamente dall'attività e procedere con staging e lancio senza dipendere dalla trattativa per `studioinfermieristico.it`. La trattativa termina entro il 15 agosto 2026 e l'offerta non supera 50 euro. Se il dominio generico viene acquisito con trasferimento completo, potrà diventare il dominio principale e `scstudioinfermieristico.it` reindirizzerà ad esso; altrimenti `scstudioinfermieristico.it` resta il dominio definitivo.
- Motivo: proteggere il naming approvato `S.C. Studio Infermieristico`, evitare che un dominio in vendita condizioni il calendario del progetto e mantenere contenuto il costo di un vantaggio soprattutto mnemonico, non determinante per la SEO.
- Conseguenze: `scstudioinfermieristico.it` è stato registrato il 20 luglio 2026 ed è sotto il controllo diretto dell'attività, con rinnovo automatico, autenticazione a due fattori, blocco trasferimento, protezione dei dati e DNSSEC attivi. La casella `info@scstudioinfermieristico.it` è operativa su Zimbra Starter; invio e ricezione sono stati provati e SPF, DKIM e DMARC risultano validi. Lo staging iniziale usa l'indirizzo Render; canonical, Analytics e materiali di lancio vengono configurati sul dominio definitivo dopo l'esito della trattativa, senza posticipare le attività tecniche.
- Collegamenti: `BRAND_SYSTEM.md`, `ROADMAP.md`, `OPERATIONS.md`.

## D-028 — URL pubblico del corso di accompagnamento

- Data: 2026-07-20.
- Stato: approvata.
- Decisione: usare `/corso-accompagnamento-nascita` come URL pubblico della pagina editoriale del corso e mantenere `/prima-della-nascita` soltanto come redirect permanente.
- Motivo: allineare l'indirizzo al naming approvato del servizio e distinguerlo dal modulo privato di iscrizione al percorso completo.
- Conseguenze: navigazione e mappa del sito puntano al nuovo URL; i collegamenti già condivisi continuano a funzionare tramite redirect `301`.
- Collegamenti: `BRAND_SYSTEM.md`, `SITE_MAP_AND_FLOWS.md`, `app.py`, `templates/base.html`.

## D-029 — Infrastruttura Render per staging e produzione

- Data: 2026-07-20.
- Stato: approvata.
- Decisione: usare Render nella regione di Francoforte con un Web Service Flask e PostgreSQL nella stessa regione. Lo staging iniziale usa istanze gratuite, URL `onrender.com`, HTTPS gestito, autenticazione HTTP applicativa e blocco globale dell'indicizzazione; il dominio pubblico non viene collegato durante lo staging. Prima della scadenza del database gratuito, l'ambiente destinato alla produzione passa almeno a Web Service Starter e PostgreSQL Basic-256mb con storage adeguato.
- Motivo: ottenere rapidamente un ambiente PostgreSQL realistico e accessibile ai soli tester, conservando un percorso di upgrade diretto e senza acquistare hosting duplicato presso il registrar.
- Conseguenze: il database gratuito scade 30 giorni dopo la creazione e non contiene dati reali; il servizio gratuito non viene usato per collaudare SMTP sulle porte bloccate. I segreti restano nelle variabili Render, l'auto-deploy è disattivato e ogni pubblicazione è intenzionale. L'HTTPS dei domini Render e personalizzati è gestito dalla piattaforma. Il dominio principale e i redirect restano disciplinati da D-027.
- Collegamenti: `OPERATIONS.md`, `ROADMAP.md`, `render.yaml`.

## D-030 — Backup PostgreSQL gestito ed esterno

- Data: 2026-07-20.
- Stato: approvata.
- Decisione: prima di accettare dati reali, usare un database Render a pagamento con point-in-time recovery e affiancargli un backup logico giornaliero cifrato sul PC controllato direttamente dall'attività. Conservare 14 giorni di copie giornaliere, 8 settimane di copie settimanali e 12 mesi di copie mensili; eseguire un restore test almeno ogni mese e prima di modifiche rischiose.
- Motivo: il database gratuito non offre backup; il solo PC locale non protegge da indisponibilità, guasti o errore umano su Render, mentre il solo PITR conserva una finestra breve e resta presso lo stesso fornitore.
- Conseguenze: il PC deve avere FileVault, account protetto, spazio monitorato e disponibilità durante l'esecuzione. URL del database e password di cifratura restano nel Portachiavi macOS; la password di recupero ha una copia offline separata. I dump sono cifrati prima della conservazione, accompagnati da checksum e ripristinabili soltanto in un database vuoto. RPO esterno massimo 24 ore e obiettivo RTO entro 8 ore lavorative.
- Collegamenti: `OPERATIONS.md`, `ROADMAP.md`, `scripts/backup_postgres.sh`, `scripts/restore_postgres.sh`.

## D-031 — Listino infermieristico ricercabile per tipologia

- Data: 2026-07-21.
- Stato: approvata.
- Decisione: organizzare `/prestazioni-infermieristiche` nelle quattro tipologie del listino approvato, usando sezioni espandibili e una ricerca client-side progressiva. La prima tipologia resta aperta all’arrivo e l’intero contenuto rimane consultabile senza JavaScript.
- Motivo: rendere leggibile un catalogo di oltre trenta prestazioni anche su mobile, senza trasformare la pagina in una griglia di card equivalenti o nascondere le informazioni ai dispositivi assistivi.
- Conseguenze: il form `/prenota` usa lo stesso elenco aggiornato e ogni prestazione selezionabile blocca uno slot uniforme di 30 minuti; le prestazioni a domicilio restano fuori dalla prenotazione diretta e richiedono valutazione manuale; tariffe variabili, materiali, distanza e prescrizione sono chiariti prima dell’azione. Il filtro apre soltanto le tipologie con risultati e comunica il numero di corrispondenze.
- Collegamenti: `CONTENT_AND_ASSETS.md`, `SITE_MAP_AND_FLOWS.md`, `templates/prestazioni_infermieristiche.html`, `static/css/prestazioni.css`, `static/js/prestazioni-filter.js`.

## D-032 — WhatsApp solo come contatto contestuale

- Data: 2026-07-21.
- Stato: approvata.
- Decisione: non mostrare un widget WhatsApp globale. Il contatto resta disponibile soltanto nei punti in cui il flusso lo prevede: persone indecise sulla consulenza del sonno, aziende o gruppi, assenza di date e richieste informative dopo la nascita.
- Motivo: evitare una CTA concorrente e indistinta accanto ai moduli dedicati per prestazioni, corsi e call sul sonno.
- Conseguenze: le CTA WhatsApp contestuali sono tracciate singolarmente; la barra mobile compare soltanto nelle pagine con una prossima azione specifica e non rinvia alla pagina corrente.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `templates/base.html`, `static/js/conversion-tracking.js`.

## D-033 — Tre formule sonno e prezzi visibili

- Data: 2026-07-21.
- Stato: approvata per la fase di lancio.
- Decisione: presentare prima della prenotazione `Consulenza mirata` a 75 €, `Percorso sonno personalizzato` a 180 € e `Percorso sonno con affiancamento` a 320 €. Il percorso base comprende tre call da 60-75 minuti e diario; quello con affiancamento aggiunge 60 giorni di WhatsApp, dal lunedì al venerdì, con massimo tre confronti raggruppati a settimana e risposta entro il giorno lavorativo successivo. Entrambi durano orientativamente 60 giorni e devono chiudersi entro 75 salvo indisponibilità di Selene.
- Motivo: evitare sorprese economiche prima della call, distinguere il valore dell'assistenza asincrona e mantenere il carico coerente con un compenso lordo minimo di 25-30 € l'ora.
- Conseguenze: la landing resta `call-first` ma rende confrontabili contenuti e prezzi; la call gratuita dura 20 minuti e non eroga consulenza. Dopo i primi cinque percorsi vengono misurati tempo di call, diario e messaggi prima di confermare o correggere i prezzi. Il claim `consulente certificata` resta sospeso finché gli attestati non vengono verificati.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/consulenze_online.html`, `static/css/consulenza.css`.

## D-034 — Pagamento, cancellazione e recesso delle consulenze sonno

- Data: 2026-07-21.
- Stato: approvata sul piano commerciale; testo contrattuale da validare.
- Decisione: pagamento anticipato tramite collegamento privato e conferma del posto al pagamento; l'accettazione finale del caso spetta a Selene. Se la rateizzazione esterna non è concessa, il percorso base usa 75 € + 75 € + 30 €; il percorso con affiancamento usa 145 € + 145 € + 30 €, includendo due blocchi WhatsApp anticipati da 70 €. La parte WhatsApp interrotta si valorizza pro quota a 70 € / 30 giorni. Cancellazione e riprogrammazione tardive comportano il 50%; il no-show perde la quota; è concesso un solo spostamento. L'indisponibilità di Selene consente riprogrammazione oppure rimborso della parte non erogata. Il servizio può essere regalato, ma il contratto viene accettato da un genitore o tutore: chi firma dichiara la propria responsabilità genitoriale o tutela e, in caso di responsabilità condivisa, di avere informato e ottenuto il consenso dell'altro genitore; l'affido esclusivo viene dichiarato sulla base del relativo provvedimento.
- Motivo: collegare pagamenti e rimborsi a componenti riconoscibili del servizio e proteggere il tempo riservato senza applicare automaticamente la perdita totale per un preavviso tardivo.
- Conseguenze: per appuntamenti del lunedì la scadenza gratuita è venerdì alle 18; da martedì a sabato è 24 ore prima, anticipata alle 18 dell'ultimo giorno lavorativo se cade in un festivo. Prima dell'attivazione servono condizioni validate, richiesta esplicita di avvio entro il termine di recesso e presa d'atto coerente con l'effettiva esecuzione del servizio.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `ROADMAP.md`, futuro checkout privato.

## D-035 — Qualificazione, promemoria e campagna Meta del sonno

- Data: 2026-07-21.
- Stato: approvata.
- Decisione: la prenotazione raccoglie soltanto i dati necessari a verificare fascia 0-12 mesi, ruolo di genitore/tutore, difficoltà, durata, obiettivo, comprensione del perimetro educativo e presa visione dei prezzi. Le call sono disponibili anche il sabato. Email e calendario prevengono le assenze; WhatsApp è facoltativo, usa template organizzativi neutrali e non contiene informazioni del bambino. La campagna iniziale è nazionale su Meta/Instagram, con tetto di 200 €, checkpoint dopo 100 € e due creatività iniziali su risvegli frequenti e addormentamento con forte supporto.
- Motivo: aumentare la percentuale di call effettivamente svolte, evitare richieste fuori ambito e apprendere dal primo budget senza suddividerlo fra servizi o pubblici diversi.
- Conseguenze: KPI canonici sono costo per call prenotata, presenza, costo per call svolta, conversione call svolta → cliente e costo effettivo per cliente. Gli annunci vengono rallentati a 10 call settimanali. Meta riceve eventi soltanto dopo consenso; l'email resta il fallback se WhatsApp fallisce. L'attuale numero telefonico non viene migrato in modo rischioso: si prova la coesistenza ufficiale e, se non disponibile, si usa un numero separato per l'automazione.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `CONTENT_AND_ASSETS.md`, `app.py`.

## Modello per nuove decisioni

```markdown
## D-XXX — Titolo

- Data: AAAA-MM-GG.
- Stato: proposta | approvata | sostituita.
- Decisione:
- Motivo:
- Conseguenze:
- Collegamenti:
```

Una decisione sostituita non va cancellata: indicare quale nuova decisione la rimpiazza.
