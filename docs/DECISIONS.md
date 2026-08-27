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

- Stato: approvata come principio generale; aggiornata da D-033 per la landing sonno.
- Decisione: comunicare prima valore e appropriatezza; mostrare i prezzi soprattutto nei materiali destinati a famiglie già interessate. Per la consulenza del sonno, D-033 introduce l'eccezione esplicita dei tre prezzi visibili prima della prenotazione.
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
- Stato: superata dalla D-037 il 2026-07-28 per il redesign a scene singole.
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
- Stato: approvata per la fase di validazione; budget, creatività e soglia di capacità sono stati definiti successivamente da D-035.
- Decisione: promuovere per tre mesi la consulenza del sonno 0-12 mesi attraverso annunci e contenuti social che portano alla scelta diretta dello slot. Il servizio resta nazionale; Abruzzo e regioni confinanti possono essere un limite tattico iniziale della distribuzione pubblicitaria soltanto per controllare la spesa. WhatsApp resta secondario per chi è indeciso.
- Motivo: raccogliere evidenze sull'intera fascia coperta dalla formazione di Selene, ridurre l'attrito tra annuncio e call e costruire prove specifiche per un servizio che non dispone ancora di testimonianze proprie.
- Conseguenze: l'obiettivo interno è arrivare ad almeno tre testimonianze reali, autorizzate e pubblicabili al mese sulla consulenza del sonno; non si promettono risultati e non si usano testimonianze di altri servizi. Il funnel misura almeno slot prenotato, call confermata, call svolta, formula scelta e consenso alla testimonianza. Budget, checkpoint, creatività iniziali e arresto a dieci call settimanali non sono più questioni aperte: sono disciplinati da D-035 e dai documenti di campagna; i costi effettivi restano invece da validare con il test.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `locandine.md`.

## D-027 — Dominio operativo indipendente dalla trattativa

- Data: 2026-07-20.
- Stato: approvata; l’alternativa condizionata è chiusa da D-074.
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
- Stato: sostituita in parte da D-061 per la topologia di produzione; restano valide le regole sullo staging gratuito.
- Decisione: usare Render nella regione di Francoforte con un Web Service Flask e PostgreSQL nella stessa regione. Lo staging iniziale usa istanze gratuite, URL `onrender.com`, HTTPS gestito, autenticazione HTTP applicativa e blocco globale dell'indicizzazione; il dominio pubblico non viene collegato durante lo staging. Prima della scadenza del database gratuito, l'ambiente destinato alla produzione passa almeno a Web Service Starter e PostgreSQL Basic-256mb con storage adeguato.
- Motivo: ottenere rapidamente un ambiente PostgreSQL realistico e accessibile ai soli tester, conservando un percorso di upgrade diretto e senza acquistare hosting duplicato presso il registrar.
- Conseguenze: il database gratuito scade 30 giorni dopo la creazione e non contiene dati reali; il 30 luglio 2026 l'attività ha confermato di non avervi mai inserito dati di pazienti, famiglie o minori. Il servizio gratuito non viene usato per collaudare SMTP sulle porte bloccate. I segreti restano nelle variabili Render, l'auto-deploy è disattivato e ogni pubblicazione è intenzionale. L'HTTPS dei domini Render e personalizzati è gestito dalla piattaforma. Il dominio principale e i redirect restano disciplinati da D-027.
- Aggiornamento: la previsione originaria di portare a pagamento le risorse di staging non è più in vigore. D-061 impone Web Service e PostgreSQL nuovi, vuoti e separati per la produzione; lo staging gratuito non viene promosso, copiato o usato per dati reali.
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
- Stato: approvata; la sola regola sulla durata uniforme è sostituita da D-062.
- Decisione: organizzare `/prestazioni-infermieristiche` nelle quattro tipologie del listino approvato, usando sezioni espandibili e una ricerca client-side progressiva. La prima tipologia resta aperta all’arrivo e l’intero contenuto rimane consultabile senza JavaScript.
- Motivo: rendere leggibile un catalogo di oltre trenta prestazioni anche su mobile, senza trasformare la pagina in una griglia di card equivalenti o nascondere le informazioni ai dispositivi assistivi.
- Conseguenze: il form `/prenota` usa un unico selettore gerarchico: su desktop il passaggio del mouse o il focus sulla tipologia apre il relativo sottomenu; su dispositivi touch la tipologia si apre al tocco. Subito prima dell’invio mostra un riepilogo con prestazione, categoria e tariffa indicativa in studio. Ogni richiesta blocca inizialmente 30 minuti; D-062 disciplina la durata effettiva scelta dall'admin prima della conferma. Le prestazioni a domicilio restano fuori dalla prenotazione diretta e richiedono valutazione manuale; tariffe variabili, materiali, distanza e prescrizione sono chiariti prima dell’azione. Il filtro apre soltanto le tipologie con risultati e comunica il numero di corrispondenze.
- Collegamenti: `CONTENT_AND_ASSETS.md`, `SITE_MAP_AND_FLOWS.md`, `templates/prestazioni_infermieristiche.html`, `static/css/prestazioni.css`, `static/js/prestazioni-filter.js`.

## D-032 — WhatsApp solo come contatto contestuale

- Data: 2026-07-21.
- Stato: approvata; aggiornata dalla D-053 e dalla D-057.
- Decisione: non mostrare un widget WhatsApp globale. Il contatto resta disponibile soltanto nei punti in cui il flusso lo prevede: persone indecise sulla consulenza del sonno, aziende o gruppi e persone che non trovano una data adatta. Quando esiste il modulo specifico per l'interesse ai corsi, questo resta l'azione principale.
- Motivo: evitare una CTA concorrente e indistinta accanto ai moduli dedicati per prestazioni, corsi e call sul sonno.
- Conseguenze: le CTA WhatsApp contestuali sono tracciate singolarmente; la barra mobile compare soltanto nelle pagine con una prossima azione specifica e non rinvia alla pagina corrente.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `templates/base.html`, `static/js/conversion-tracking.js`.

## D-033 — Tre formule sonno e prezzi visibili

- Data: 2026-07-21.
- Stato: approvata per la fase di lancio.
- Decisione: presentare prima della prenotazione `Consulenza mirata` a 75 €, `Percorso sonno personalizzato` a 180 € e `Percorso sonno con affiancamento` a 320 €. Il percorso base comprende tre call da 60-75 minuti e diario; quello con affiancamento aggiunge 60 giorni di WhatsApp, dal lunedì al venerdì, con massimo tre confronti raggruppati a settimana e risposta entro il giorno lavorativo successivo. Entrambi durano orientativamente 60 giorni e devono chiudersi entro 75 salvo indisponibilità di Selene.
- Motivo: evitare sorprese economiche prima della call, distinguere il valore dell'assistenza asincrona e mantenere il carico coerente con un compenso lordo minimo di 25-30 € l'ora.
- Conseguenze: la landing resta `call-first` ma rende confrontabili contenuti e prezzi; la call gratuita dura 20 minuti e non eroga consulenza. Dopo i primi cinque percorsi vengono misurati tempo di call, diario e messaggi prima di confermare o correggere i prezzi. La credenziale pertinente è definita dalla D-052.
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
- Stato: approvata per qualificazione e campagna; tutte le clausole sui promemoria WhatsApp sono superate dalla D-036.
- Decisione: la prenotazione raccoglie soltanto i dati necessari a verificare fascia 0-12 mesi, ruolo di genitore/tutore, difficoltà, durata, obiettivo, comprensione del perimetro educativo e presa visione dei prezzi. Le call sono disponibili anche il sabato. Email e calendario prevengono le assenze; WhatsApp è facoltativo, usa template organizzativi neutrali e non contiene informazioni del bambino. La campagna iniziale è nazionale su Meta/Instagram, con tetto di 200 €, checkpoint dopo 100 € e due creatività iniziali su risvegli frequenti e addormentamento con forte supporto.
- Motivo: aumentare la percentuale di call effettivamente svolte, evitare richieste fuori ambito e apprendere dal primo budget senza suddividerlo fra servizi o pubblici diversi.
- Conseguenze: KPI canonici sono costo per call prenotata, presenza, costo per call svolta, conversione call svolta → cliente e costo effettivo per cliente. Gli annunci vengono rallentati a 10 call settimanali. Meta riceve eventi soltanto dopo consenso. Il fallback email, la coesistenza e l'eventuale secondo numero descritti nella decisione originaria non sono più operativi: la D-036 ha eliminato integralmente l'automazione WhatsApp dei promemoria.
- Collegamenti: `PROJECT_BRIEF.md`, `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `CONTENT_AND_ASSETS.md`, `app.py`.

## D-036 — Promemoria delle call soltanto via email

- Data: 2026-07-22.
- Stato: approvata.
- Decisione: eliminare i promemoria automatici WhatsApp e inviare le notifiche organizzative delle call esclusivamente via email, mantenendo i controlli a 24 ore e 2 ore e la prevenzione dei duplicati. WhatsApp resta soltanto un contatto umano contestuale e il canale incluso nel percorso sonno con affiancamento.
- Motivo: evitare la complessità operativa, tecnica e autorizzativa della WhatsApp Business Platform per una funzione coperta in modo adeguato dall'email.
- Conseguenze: il modulo non richiede un consenso WhatsApp; configurazione, template, credenziali, codice di invio e campi database della precedente automazione vengono rimossi. Non occorrono più Coexistence, un secondo numero o un provider WhatsApp per gestire i promemoria.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `ROADMAP.md`, `OPERATIONS.md`, `templates/prenota_call_sonno.html`, `app.py`.

## D-037 — Regia scroll della homepage differenziata per dispositivo

- Data: 2026-07-28.
- Stato: approvata; ritmo desktop aggiornato dalla D-044, guida laterale dalla D-045, livelli hero dalla D-046, numero di scene dalla D-048 e footer dalla D-050 il 2026-07-29.
- Decisione: trattare la homepage come una sequenza di sette scene autonome, oppure otto quando esistono date future: apertura, corsi, sonno, eventuali date, nascita, metodo, attività e scelta finale. Quando lo snap è attivo, ogni scena occupa esattamente lo spazio visibile sotto l'header e non richiede né consente uno scorrimento interno; il footer mantiene invece altezza e scorrimento naturali. Corsi e sonno hanno due scene editoriali distinte, con priorità visiva ai corsi. La linea rossa laterale indica la scena attiva. Il parallax fotografico resta circoscritto all'apertura.
- Motivo: far corrispondere ogni arresto dello scroll a un solo argomento e a una sola schermata, eliminando l'ambiguità di uno snap che conteneva sezioni più alte del viewport.
- Conseguenze: snap e guida laterale si attivano soltanto da 1024 px di larghezza e 640 px di altezza, con movimento non ridotto. All'ingresso la guida si costruisce con una cucitura rossa temporanea, seguita dall'apertura progressiva dei tre capitoli e dal segno della scena attiva; la cucitura scompare al termine e non diventa una seconda linea decorativa permanente. Tra 640 e 840 px la composizione riduce spazi e dimensioni fotografiche per conservare una scena per schermata; sotto una delle due soglie, con `prefers-reduced-motion` o senza JavaScript, la homepage torna a essere una pagina continua e tutti i contenuti restano visibili. La guida scompare quando entra il footer naturale. I livelli fotografici definitivi della hero sono descritti nella D-046.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-038 — Passaggio di luce tra gli organi della homepage

- Data: 2026-07-28.
- Stato: superata dalla D-039 il 2026-07-28.
- Decisione: collegare le prime tre scene con quattro accensioni puntuali sugli organi reali nelle fotografie: cuore in mano nella hero, cuore e cistifellea sulla parete nella scena corsi, cistifellea in mano nella scena sonno. Su desktop un impulso percorre la linea rossa della guida laterale quando cambia la scena; su mobile resta soltanto l'accensione locale. L'effetto si attiva una volta all'arrivo, senza oscillazioni, particelle o cicli continui.
- Motivo: trasformare gli organi all'uncinetto in un filo narrativo riconoscibile e proprio dello studio, mantenendo il movimento legato al contenuto invece di aggiungere una decorazione generica.
- Conseguenze: dopo il confronto dei 143 originali disponibili restano i tre scatti correnti, perché formano la sequenza più chiara. Con `prefers-reduced-motion` l'evidenziazione è statica e la linea non viaggia; il significato e la navigazione non dipendono dall'animazione.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-039 — Filo materico continuo come regia della homepage

- Data: 2026-07-28.
- Stato: superata dalla D-040 il 2026-07-28.
- Decisione: sostituire il punto luce con un unico filo rosso materico che nasce dal cuore della hero e segue lo scroll. I raccordi compaiono soltanto durante il passaggio fra scene e si cancellano in senso inverso, così i testi non vengono attraversati. Sono escluse figure simboliche o decorative: il filo compie soltanto gesti fisici, con un giro incompleto attorno a ciascun organo e una curva morbida fra cuore e cistifellea nella scena corsi. Il filo passa davanti e dietro agli organi tramite maschere SVG. L'header reagisce alla scena e la navigazione laterale usa etichette e brevi tratti, senza una seconda linea continua.
- Motivo: rendere percepibile un movimento che attraversa le scene e trasformare il manufatto all'uncinetto in una regia propria dello studio, invece di applicare un'animazione locale trasferibile a qualunque fotografia.
- Conseguenze: il prototipo usa SVG, CSS e JavaScript vanilla, senza Three.js o nuove dipendenze. Il filo digitale combina trefolo irregolare, ombra stretta, variazioni tonali e fibre spezzate; la micro-apertura dura circa mezzo secondo e viene mostrata una volta per sessione. Su mobile il filo termina dopo le prime tre scene; con movimento ridotto le figure sono statiche e lo snap viene disattivato. Per la massima fedeltà materica serviranno comunque fotografie macro del filo reale. Prima di estendere il sistema alle altre cinque scene vanno validati ritmo, spessore, forme e resa del materiale.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-040 — Staffetta degli organi e profondità fotografica

- Data: 2026-07-28.
- Stato: ripristinata e rifinita dalla D-043 il 2026-07-29.
- Decisione: rimuovere integralmente il filo dalla homepage. Nei passaggi hero-corsi e corsi-sonno un ritaglio fotografico dell'organo parte dalla posizione reale nella scena uscente, segue una traiettoria breve e confluisce nella posizione reale della scena entrante, con dissolvenza fra i due scatti. Dalla scena sonno in poi il passaggio usa una profondità fotografica più sobria: la scena uscente arretra e perde leggermente fuoco mentre quella entrante torna alla scala naturale. All'arresto dello snap non resta alcun livello sovrapposto.
- Motivo: conservare gli organi all'uncinetto come elemento distintivo, assegnando al movimento una destinazione evidente e rimuovendo segni grafici che interferivano con fotografie e testi.
- Conseguenze: l'effetto usa CSS e JavaScript vanilla e ritaglia dinamicamente le fotografie già presenti, senza duplicare asset. La staffetta è riservata al desktop con snap; mobile mantiene lo scroll libero e il movimento ridotto disattiva sia staffetta sia profondità. Il percorso deve funzionare nello stesso modo anche tornando allo snap precedente.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-041 — Snap desktop con ritmo coreografico

- Data: 2026-07-29.
- Stato: superata dalla D-042 il 2026-07-29.
- Decisione: sostituire la durata non controllabile dello snap nativo con una regia JavaScript limitata alla homepage desktop. Rotella, trackpad, tastiera e navigazione laterale avanzano fra le scene con accelerazione e frenata morbide; un passaggio singolo dura circa 1,05 secondi, mentre i salti fra scene lontane sono limitati a 1,38 secondi. Durante il tragitto lo snap CSS viene sospeso e riattivato soltanto sul punto di arresto esatto.
- Motivo: lasciare il tempo di leggere la staffetta degli organi e la profondità fotografica, evitando sia l'arresto brusco deciso dal browser sia una navigazione lenta e vischiosa.
- Conseguenze: un gesto produce un solo avanzamento di scena e gli ulteriori impulsi vengono assorbiti fino al termine del passaggio. Mobile conserva lo scroll nativo libero; `prefers-reduced-motion` disattiva sia la regia sia lo snap. Link, pulsanti e campi mantengono il comportamento da tastiera previsto.
- Collegamenti: `DECISIONS.md` D-037 e D-040, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-042 — Staffetta tipografica tra le prime scene

- Data: 2026-07-29.
- Stato: superata dalla D-043 il 2026-07-29.
- Decisione: usare le parole dei titoli come unico passaggio animato tra le prime quattro scene. `fare` diventa `preparati`, `contano` diventa `insieme` e `insieme` confluisce nel primo giorno cliccabile del calendario. Se non esistono corsi programmati, l'ultimo passaggio termina sulla parola `data` dello stato vuoto. Durante il movimento la parola originale lascia il posto a un livello tipografico temporaneo che cambia posizione, dimensione e testo, poi torna a essere contenuto reale nella scena successiva.
- Motivo: collegare le scene attraverso il tono editoriale dello studio senza sovrapporre fotografie ritagliate, sfocature o segni grafici ai contenuti.
- Conseguenze: lo snap torna nativo e non intercetta rotella, trackpad o tastiera. La staffetta compare soltanto durante lo scorrimento desktop e scompare agli arresti; mobile e movimento ridotto mantengono testi normali e nessun livello volante. Il titolo dei corsi diventa `Arrivare preparati ai momenti che contano.` per dare alle due parole una funzione naturale nella frase.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`, `static/js/calendario.js`.

## D-043 — Ripristino del sistema ibrido con organi scontornati

- Data: 2026-07-29.
- Stato: approvata; ritmo aggiornato dalla D-044 il 2026-07-29.
- Decisione: ripristinare la staffetta fotografica della D-040 e rimuovere integralmente la staffetta tipografica. Il cuore e la cistifellea non viaggiano più dentro medaglioni o ritagli circolari: ogni inquadratura usa una sagoma dedicata che segue il profilo del manufatto. Il ritaglio mantiene i pixel della fotografia originale e usa soltanto un'ombra aderente al contorno. Dalla scena sonno in poi resta la profondità fotografica della D-040.
- Motivo: mantenere gli organi all'uncinetto come firma visiva senza mostrare il fondo bianco della fotografia dentro una forma estranea all'oggetto.
- Conseguenze: le sagome sono definite nel codice con `clip-path` separati per cuore e cistifellea nelle rispettive fotografie. Non servono nuovi asset o immagini generate. La staffetta è riservata al desktop e scompare agli arresti. Mobile e movimento ridotto non mostrano né staffetta né profondità.
- Collegamenti: `DECISIONS.md` D-040 e D-042, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-044 — Ritmo coreografico calibrato sul sistema ibrido

- Data: 2026-07-29.
- Stato: implementata; comportamento rappresentativo verificato a 1440 e 390 px.
- Decisione: rallentare i passaggi fra gli snap desktop con una durata di 0,85 secondi e una curva sinusoidale continua. Un gesto di rotella, trackpad o tastiera avanza di una sola scena; gli impulsi residui vengono assorbiti fino all'arresto. I salti richiesti dalla navigazione laterale restano più brevi di 1,15 secondi anche quando attraversano più scene.
- Motivo: rendere leggibile la traiettoria degli organi e dare respiro ai passaggi di profondità senza riproporre la sensazione vischiosa del precedente prototipo da 1,05 secondi.
- Conseguenze: durante il tragitto lo snap CSS viene sospeso e riattivato sul punto di arresto esatto. Scroll, staffetta e profondità condividono un solo ciclo di rendering; geometrie fotografiche e punti di arresto vengono misurati prima del passaggio, evitando ricalcoli di layout durante l'animazione. Gli organi seguono direttamente la curva dello snap, con dissolvenza estesa fra le due fotografie e ridimensionamento affidato a trasformazioni composite anziché a variazioni di larghezza e altezza. Mobile conserva lo scroll libero; `prefers-reduced-motion` mantiene il comportamento nativo e disattiva gli effetti. Link, pulsanti e campi non vengono intercettati dalla navigazione da tastiera.
- Collegamenti: `DECISIONS.md` D-037, D-041 e D-043, `ROADMAP.md`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-045 — Guida laterale organizzata per capitoli

- Data: 2026-07-29.
- Stato: implementata; comportamento rappresentativo verificato a 1440 e 390 px.
- Decisione: organizzare la navigazione laterale della homepage in tre capitoli: `Orientarsi` per apertura, corsi, sonno e date; `Conoscere` per nascita, metodo e attività; `Scegliere` per la scena finale. Corsi e sonno mantengono tacche più evidenti anche quando non sono attivi. Il nome della scena corrente fa parte della riga della guida, senza un riquadro sospeso.
- Motivo: rendere visibile la gerarchia del racconto e impedire che otto indicatori equivalenti attribuiscano lo stesso peso ai due pilastri commerciali, alle prove di fiducia e alla scelta finale.
- Conseguenze: il capitolo corrente viene aggiornato insieme alla scena; hover e focus continuano a mostrare il nome di ogni destinazione. La guida resta disponibile soltanto nel layout desktop con snap e non modifica lo scroll libero mobile.
- Collegamenti: `DECISIONS.md` D-037, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-046 — Livelli fotografici definitivi della hero

- Data: 2026-07-29.
- Stato: implementata; comportamento rappresentativo verificato a 1440 e 390 px.
- Decisione: mantenere composizione e intensità del parallax della hero, sostituendo il fondale prototipale e la sagoma SVG con due livelli ricavati dall'originale `SELENE-16.jpg` a 6000×4000 px. Il fondale conserva colore e grana della parete dello scatto; il primo piano usa una maschera fotografica per-pixel di Selene.
- Motivo: evitare che il parallax faccia percepire Selene come una figura ritagliata e conservare i dettagli irregolari di capelli e spalle che un tracciato geometrico non può seguire.
- Conseguenze: il fallback resta la fotografia completa a 1920×1280; con JavaScript attivo vengono caricati un JPEG di fondale e un WebP trasparente della stessa misura. Non cambiano testi, proporzioni, intensità del movimento o comportamento mobile. L'originale ad alta risoluzione resta fuori dal repository.
- Collegamenti: `DECISIONS.md` D-037, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`.

## D-047 — Credenziali fuori dalla scena corsi

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: rimuovere dalla scena corsi la fascia con `Infermiera OPI Pescara`, `Attività pratiche` e `In presenza`. Formato e luogo diventano l'intestazione `Corsi pratici in presenza · Montesilvano`; l'iscrizione OPI resta verificabile nei contenuti dedicati al profilo professionale, senza essere presentata come elemento distintivo dell'offerta.
- Motivo: l'iscrizione all'Ordine è una credenziale necessaria della professione, non un beneficio differenziante; pratica e luogo erano già comunicati dalla fotografia e dai testi. La fascia duplicava informazioni e assumeva l'aspetto di una tabella amministrativa.
- Conseguenze: la scena corsi contiene una sola gerarchia formata da fotografia, intestazione, titolo, descrizione, corsi e azione. Non viene introdotto un tratto rosso sostitutivo privo di funzione; lo spazio recuperato migliora il respiro della schermata anche sui laptop compatti.
- Collegamenti: `BRAND_SYSTEM.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `static/css/homepage.css`.

## D-048 — Scene editoriali adattive e movimento legato al contenuto

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: organizzare la scena corsi in due famiglie, `Sicurezza` e `Nascita e crescita`, senza trasformare i quattro collegamenti in schede equivalenti. La scena Date viene renderizzata, inclusa nella guida e caricata con il relativo JavaScript soltanto quando esistono date future non annullate; negli altri casi la raccolta di interesse conclude la scena corsi. La squadra del percorso nascita diventa una firma continua lungo un solo asse. Metodo e prova vengono riuniti nella sequenza `Ascolto` → `Mettiamo ordine` → `Scegliamo il passo` → `Strumenti che restano`, con una sola testimonianza completa in homepage.
- Motivo: ridurre l'effetto catalogo e amministrativo, mantenere una schermata per snap e fare in modo che ogni elemento della homepage contribuisca al racconto invece di occupare spazio per completezza formale.
- Conseguenze: la homepage contiene sette scene quando il calendario è vuoto e otto quando sono disponibili date. Dopo la staffetta degli organi, ogni transizione usa lo stesso principio di scala, fuoco e completamento progressivo applicato al contenuto della scena: bordo del calendario, fotografia del team, linea del metodo, feed delle attività e separazione delle due scelte finali. Mobile mantiene composizione completa e scroll libero; il movimento ridotto mostra immediatamente ogni elemento nello stato finale. Il secondo feedback del percorso nascita viene conservato nella pagina dedicata al corso.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `templates/homepage.html`, `templates/prima_della_nascita.html`, `static/css/homepage.css`, `static/css/accompagnamento.css`, `static/js/home-scroll-motion.js`.

## D-049 — Feed Instagram vivo e senza cornice concorrente

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: mostrare automaticamente gli ultimi sei post Instagram con il layout flessibile di Behold: tre colonne quadrate su desktop e due colonne in rapporto 4:5 su mobile. I contenuti hanno angoli al 20%, overlay `#7C9A7E`, nessun bordo e aprono la galleria interna. La cornice verde, l'ombra e gli angoli asimmetrici del contenitore del sito vengono rimossi.
- Motivo: il feed deve raccontare la realtà aggiornata dello studio. I ritagli molto arrotondati sono già il gesto visivo caratterizzante; una seconda sagoma attorno all'intera griglia ne indeboliva la lettura.
- Conseguenze: il sito non forza dimensioni o trasformazioni interne del widget e mantiene soltanto il contenitore necessario al movimento della scena. Aggiornamenti e ordine dei post restano gestiti da Behold; la scena conserva titolo, contesto e collegamento al profilo Instagram.
- Collegamenti: `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `static/css/homepage.css`.

## D-050 — Scelta finale e footer come epilogo naturale

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: trasformare l'ultimo snap in due campi asimmetrici, con circa tre quinti dello spazio destinati ai corsi e due quinti alla consulenza del sonno. Ogni campo contiene una frase concreta e una sola azione; un ritaglio reale degli organi dalla fotografia dei corsi chiude il racconto visivo. Le prestazioni infermieristiche diventano una riga secondaria sotto le due scelte. Il footer non è più un punto di snap, mantiene altezza naturale e fa scomparire la guida laterale quando entra nella finestra.
- Motivo: evitare che la chiusura ripeta semplicemente la hero, rispettare la gerarchia commerciale e impedire che informazioni legali e recapiti occupino un'intera schermata vuota.
- Conseguenze: lo snap desktop termina sulla scelta finale e il successivo gesto di scorrimento entra nel footer con comportamento nativo. Su mobile il testo precede le fotografie nei due pilastri, le scelte si impilano, la galleria Instagram resta su due colonne e il footer conserva il flusso naturale. La linea rossa segnala soltanto l'inizio dei tre capitoli del racconto mobile.
- Collegamenti: `BRAND_SYSTEM.md`, `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `static/css/homepage.css`, `static/js/home-scroll-motion.js`.

## D-051 — Un linguaggio comune con regie diverse nelle pagine interne

- Data: 2026-07-29.
- Stato: implementata; resa rappresentativa verificata a 1440 e 390 px.
- Decisione: estendere alle pagine interne il ritmo editoriale, la scala tipografica, i ritagli fotografici e l'uso funzionale della linea rossa introdotti dalla nuova homepage, mantenendo però lo scroll libero. Le pagine pubbliche vengono distinte in tre modalità: narrative per servizi e contenuti, operative per moduli e questionari, di esito per conferme. Le pagine narrative mostrano un sottile avanzamento di lettura sotto l'header e una sola entrata morbida per ogni capitolo; i moduli usano superfici calme senza progressione coreografica; le conferme sono trattate come punti di arrivo. La CTA mobile fissa si ritira quando la stessa azione o la sua destinazione sono già visibili.
- Motivo: rendere riconoscibile lo stesso studio in tutti i percorsi senza trasferire lo snap dove la persona deve leggere, confrontare, usare ancore, correggere errori o compilare campi. Lo snap resta quindi una firma esclusiva della homepage.
- Conseguenze: `Chi sono`, FAQ, directory corsi e privacy abbandonano l'aspetto a griglia di schede a favore di composizioni editoriali; landing sonno, nascita, corsi e prestazioni conservano le loro gerarchie specifiche ma condividono movimento e avanzamento. Sotto 640 px lo scroll resta nativo e le composizioni si impilano; `prefers-reduced-motion` elimina le entrate. Admin, login e homepage non caricano il modulo delle pagine interne.
- Collegamenti: `BRAND_SYSTEM.md`, `SITE_MAP_AND_FLOWS.md`, `ROADMAP.md`, `templates/base.html`, `static/css/internal-pages.css`, `static/js/internal-page-motion.js`.

## D-052 — Credenziale pertinente e riferimento prudente alla SIDS

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: presentare Selene nella landing `/consulenze-online` come `infermiera e consulente del sonno infantile`, spostando fuori dalla pagina il Master in Management per le funzioni di coordinamento. Non mostrare nella landing la durata di 127 ore della formazione. Nominare la SIDS nella meta description e in una domanda frequente dedicata al sonno sicuro, usando la formulazione `riduzione del rischio` e collegando le indicazioni del Ministero della Salute.
- Motivo: la qualifica sul sonno è direttamente pertinente al servizio, mentre il Master documenta il profilo generale ma può essere interpretato come una specializzazione sul sonno. Il riferimento alla SIDS risponde a un tema importante per le famiglie senza usare paura, promesse di prevenzione o affermazioni oltre il perimetro educativo della consulenza.
- Conseguenze: metadati, dati strutturati e testo visibile della landing usano la stessa qualifica. La pagina `/chi-sono` resta invariata; le credenziali complete sono registrate nella documentazione interna per un eventuale intervento successivo.
- Collegamenti: `CONTENT_AND_ASSETS.md`, `PROJECT_BRIEF.md`, `templates/consulenze_online.html`.

## D-053 — Supporto dopo la nascita fuori dal perimetro pubblico

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: mantenere il contenuto dedicato a eventuali servizi dopo la nascita come bozza interna, senza route pubblica, collegamenti di navigazione o indicizzazione. La pagina potrà essere ripresa soltanto dopo aver definito offerta, confini, flusso e azione principale.
- Motivo: il contenuto anticipa servizi futuri che non fanno parte dell'offerta attuale e non deve sembrare prenotabile o disponibile prima della loro approvazione.
- Conseguenze: `/dopo-la-nascita` risponde con 404; il contatto WhatsApp per richieste generiche dopo la nascita non è più un punto previsto dal flusso corrente. Il template resta nel repository come bozza non raggiungibile.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `ROADMAP.md`, `app.py`, `templates/dopo_la_nascita.html`.

## D-054 — Una sola persona grammaticale nei testi di percorso

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: rivolgere i testi pubblici a una persona con il `tu`, usando `la tua famiglia` quando è necessario includere il nucleo familiare. Conservare il plurale soltanto nelle testimonianze, nei contenuti destinati realmente a coppie o gruppi e nelle azioni che Selene compie insieme alla persona. Rendere inoltre esplicita la funzione dei collegamenti: `Scopri` apre una pagina di dettaglio, mentre l'iscrizione viene nominata solo quando l'azione porta al relativo modulo.
- Motivo: evitare passaggi involontari tra singolare e plurale, soprattutto nella pagina `Chi sono`, e fare in modo che ogni pulsante anticipi correttamente ciò che succede dopo il clic.
- Conseguenze: homepage, `Chi sono`, directory corsi, consulenza del sonno, questionario, call, FAQ e prestazioni usano la stessa voce. La bozza disattivata `/dopo-la-nascita` resta esclusa dalla revisione. La precedente indicazione di non modificare `Chi sono` registrata in D-052 è superata soltanto per questa correzione editoriale.
- Collegamenti: `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `templates/chi_siamo.html`, `templates/iscrizione_corsi.html`, `templates/consulenze_online.html`.

## D-055 — Nessun vicolo cieco nei percorsi attivi

- Data: 2026-07-29.
- Stato: approvata.
- Decisione: chiudere la pagina `Chi sono` con due azioni principali, corsi e consulenza del sonno, e mantenere le prestazioni infermieristiche come collegamento secondario. Ogni pagina di conferma deve offrire almeno una via di ritorno; se un modulo privato non è disponibile, il recapito mostrato deve essere utilizzabile direttamente.
- Motivo: chi arriva in fondo a una pagina deve capire quale azione può compiere senza dover tornare all'header o cercare un recapito nel footer.
- Conseguenze: `Chi sono` non usa una barra fissa e non introduce un contatto WhatsApp generico. La conferma del percorso nascita torna alla homepage e il numero della pagina privata chiusa diventa un collegamento telefonico. Privacy resta priva di CTA commerciale perché è una pagina legale aperta dai moduli.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/chi_siamo.html`, `templates/conferma_iscrizione_accompagnamento.html`, `templates/iscrizione_accompagnamento_privata.html`.

## D-056 — Le pagine si susseguono come scene

- Data: 2026-07-29.
- Stato: implementata.
- Decisione: usare una transizione orizzontale controllata tra tutte le pagine pubbliche dello stesso sito. La homepage occupa idealmente il lato sinistro del racconto: entrando in un percorso la destinazione arriva da destra; tornando alla homepage, anche con una navigazione indietro ripristinata dalla cache del browser, la home viene rivelata da sinistra. La pagina richiesta compare direttamente dietro un sottile bordo rosso: la linea coincide con il bordo fisico della nuova schermata e ne trascina testi, immagini e superfici, invece di attraversare lo schermo da sola o aprire un ritaglio statico. Non esiste una schermata intermedia. L'header resta il riferimento stabile e, quando lo snap desktop è attivo, usa la stessa altezza di 76 px nella homepage e nelle pagine interne. La regia vale per CTA, logo, navigazione principale, menu mobile, footer e collegamenti interni nei contenuti. Ancore nella stessa pagina, collegamenti esterni e area amministrativa mantengono il comportamento standard.
- Motivo: ogni passaggio interno deve continuare lo stesso racconto, indipendentemente dal punto da cui la persona sceglie il percorso. Il bordo rosso rende leggibile il confine in movimento e conserva la funzione di guida assegnata alla firma del brand.
- Conseguenze: Flask continua a servire pagine complete e non viene introdotto un router client-side. Per i collegamenti pubblici idonei, uno script prepara una copia isolata e non interattiva della destinazione, senza eseguirne gli script, e la fa scorrere sopra la pagina corrente: il vecchio contenuto scompare quindi in modo progressivo, seguendo il bordo rosso. L'anteprima conserva l'intero viewport e lo spazio occupato dall'header, rendendo invisibile soltanto la sua copia sotto l'header stabile: misure `vh`, ritagli fotografici e posizione dei contenuti coincidono così con il documento definitivo. Se il link contiene un'ancora verso un'altra pagina, anche la copia viene posizionata sul bersaglio, evitando un passaggio dalla hero prima del contenuto richiesto. Il movimento può iniziare quando CSS, font e immagini del primo viewport sono pronti, senza attendere mappe o contenuti esterni collocati più in basso; la hero della homepage usa già nell'anteprima la stessa composizione fotografica a livelli della pagina caricata. Concluso il movimento, la navigazione reale sostituisce la copia senza ripetere l'entrata orizzontale né la rivelazione dei contenuti già visibili; le animazioni dei capitoli successivi restano disponibili durante lo scroll. Tornando alla homepage, il filo attivo nell'header si apre da destra verso sinistra e l'indicatore delle scene esegue la propria apertura a cucitura, invece di apparire istantaneamente. La preparazione richiede una richiesta HTML aggiuntiva per clic; se non termina entro il tempo previsto o non è disponibile, il collegamento apre comunque la destinazione e usa l'entrata direzionale semplice. La stessa entrata di riserva gestisce la cronologia del browser. Il sistema usa soltanto codice client e asset statici: non aggiunge processi, dipendenze o servizi a pagamento e non cambia il piano Render approvato, pur producendo un modesto aumento di richieste HTML e banda. Questa regia sostituisce la View Transition API nativa, che poteva annullare l'animazione in modo non deterministico. `prefers-reduced-motion` esclude l'effetto e lascia la navigazione immediata; errori JavaScript o CSS non impediscono ai collegamenti di funzionare.
- Collegamenti: `templates/base.html`, `static/css/page-transitions.css`, `static/js/page-transitions.js`.

## D-057 — Un modulo minimo per l'interesse ai corsi

- Data: 2026-07-29.
- Stato: implementata.
- Decisione: quando la homepage non contiene date future, la CTA `Lascia il tuo interesse` apre direttamente un modulo unico di ricontatto. La persona sceglie tra disostruzione pediatrica e tagli sicuri, BLSD, accompagnamento alla nascita, laboratori per l'infanzia e gioco e sviluppo. Il modulo richiede nome, telefono, tematica e consenso privacy; email e note restano facoltative. Non vengono richiesti codice fiscale, dichiarazioni per le prove pratiche o altri dati propri dell'iscrizione.
- Motivo: passare dalla CTA alla directory dei corsi aggiungeva un passaggio senza aiutare chi vuole soltanto conoscere la prossima data. Un ricontatto non è ancora un'iscrizione e deve rispettare il principio di minimizzazione dei dati.
- Conseguenze: la richiesta viene salvata nello stesso gestionale dei corsi con tipo `Da ricontattare`, zero posti occupati e tematica visibile nel titolo. Lo studio riceve l'alert email; la conferma chiarisce che una futura proposta di data non vincola all'iscrizione. I moduli specifici dei singoli corsi restano disponibili per contenuti, date aperte e richieste contestuali.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/interesse_corsi.html`, `app.py`.

## D-058 — La CTA informativa sul sonno apre il confronto delle formule

- Data: 2026-07-29.
- Stato: implementata e verificata a 1440×666 e 390×844 px.
- Decisione: nello snap sonno della homepage la CTA `Scopri la consulenza` apre direttamente la sezione `#formule` di `/consulenze-online`, dove sono presentate consulenza mirata, percorso personalizzato e percorso con affiancamento. Il collegamento secondario `Prima parliamone` continua invece ad aprire la prenotazione della call gratuita.
- Motivo: le due azioni devono mantenere funzioni diverse. `Scopri` serve a comprendere e confrontare l'offerta; la call è il passo successivo per chi desidera parlarne o scegliere uno slot.
- Conseguenze: la transizione tra pagine posiziona anche l'anteprima su `#formule`, con il titolo libero dall'header sticky; non mostra prima la hero o la CTA della call e non produce un secondo salto dopo il caricamento. Il fallback senza animazione conserva il normale comportamento dell'ancora.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `templates/homepage.html`, `templates/consulenze_online.html`, `static/js/page-transitions.js`.

## D-059 — Preproduzione privata esplicita e origine pubblica canonica

- Data: 2026-07-29.
- Stato: implementata nel codice; da attivare e collaudare su Render.
- Decisione: mantenere `APP_ENV=staging`, Basic Auth e `noindex` durante il collaudo a pagamento di SMTP e Calendar, abilitando gli invii reali soltanto con `STAGING_LIVE_INTEGRATIONS=true` e configurazione completa. In produzione richiedere `PUBLIC_BASE_URL` come origine HTTPS esplicita e usare tale origine per canonical, Open Graph, dati strutturati e link assoluti nelle email.
- Motivo: il piano gratuito deve restare incapace di inviare email per errore, mentre la preproduzione deve poter collaudare le integrazioni senza aprire il sito. L'host della richiesta non è una fonte affidabile per la SEO quando il sottodominio Render resta raggiungibile.
- Conseguenze: i fallback Gmail vengono eliminati; preproduzione e produzione rifiutano configurazioni SMTP diverse da Zimbra approvato o prive del secret file Calendar. Il dominio definitivo resta disciplinato da D-027 e viene inserito come valore esterno senza hardcoding nel codice.
- Collegamenti: `config.py`, `app.py`, `templates/base.html`, `templates/consulenze_online.html`, `OPERATIONS.md`, `ROADMAP.md`.

## D-060 — Health check operativo fuori dai limiti applicativi

- Data: 2026-07-29.
- Stato: implementata e verificata su Render.
- Decisione: mantenere `/healthz` fuori dalla Basic Auth dello staging e renderlo esente dai limiti globali di Flask-Limiter, conservando la verifica della connessione al database e la risposta `503` in caso di errore.
- Motivo: Render interroga l'endpoint ogni cinque secondi durante l'avvio. Il limite applicativo generale di 50 richieste l'ora esaurisce quindi la quota del monitor, produce falsi `429` e provoca riavvii periodici di un servizio altrimenti funzionante.
- Conseguenze: le route pubbliche e sensibili mantengono i propri limiti; soltanto l'endpoint tecnico, che non legge né modifica dati applicativi, resta sempre raggiungibile dal monitor. Il deploy `8a4ad84` ha superato 55 richieste consecutive con risposta `200` e nessun nuovo `429`; anche il riavvio successivo alla rimozione dei segreti bootstrap ha mantenuto il controllo stabile.
- Collegamenti: `app.py`, `tests/test_app.py`, `OPERATIONS.md`, `ROADMAP.md`.

## D-061 — Produzione separata e preparazione senza spesa

- Data: 2026-07-29.
- Stato: approvata; configurazione preparata, non applicata.
- Decisione: mantenere lo staging gratuito esistente come ambiente privato e creare, soltanto dopo un futuro ordine esplicito, un Web Service Starter e un PostgreSQL Basic-256mb nuovi e separati per la produzione. Il database gratuito non viene promosso né copiato. La prima accensione delle risorse definitive mantiene `APP_ENV=staging`, Basic Auth, `noindex`, email soppresse, integrazioni reali disattivate, nessun dominio e database non raggiungibile dall'esterno.
- Motivo: un database vuoto e risorse isolate riducono il rischio di trasferire dati sintetici, configurazioni di prova o credenziali dello staging e rendono più chiari rollback, collaudo e cutover.
- Conseguenze: `render.production.yaml` è un Blueprint distinto e non collegato al Blueprint attuale; contiene piani a pagamento ma non produce effetti senza selezione e sincronizzazione manuali. Il 29 luglio il pannello indicava un minimo di 13,30 USD al mese prima di eventuali imposte; il costo va riletto prima della creazione. `main` deve coincidere con il commit approvato prima dell'uso. Email reali, Calendar, DNS, passaggio a `APP_ENV=production` e apertura pubblica conservano autorizzazioni separate. Il database blocca inizialmente ogni accesso esterno; il backup locale richiederà in seguito una sorgente IP stabile e strettamente autorizzata.
- Collegamenti: `render.production.yaml`, `render.yaml`, `OPERATIONS.md`, `ROADMAP.md`, D-027, D-029, D-030, D-059.

## D-062 — Durata effettiva scelta alla conferma delle prestazioni

- Data: 2026-07-29.
- Stato: approvata, implementata e verificata localmente; collaudo reale ancora richiesto.
- Decisione: una richiesta sanitaria proveniente dal sito blocca provvisoriamente 30 minuti. Prima di confermarla Selene indica manualmente nell'admin la durata effettiva, come già fa creando un appuntamento in Arzamed. La durata viene salvata con l'appuntamento e determina l'intervallo occupato nel database e l'orario di fine su Google Calendar.
- Motivo: Arzamed pubblica su Google Calendar l'inizio e la fine effettivi e le prestazioni possono richiedere tempi diversi anche all'interno della stessa tipologia; un catalogo di durate fisse non rappresenterebbe il lavoro reale.
- Conseguenze: la conferma viene rifiutata se la durata manca, non è compresa tra 1 e 480 minuti, supera l'orario di apertura o si sovrappone a richieste, call, corsi o eventi Calendar. Le righe esistenti ricevono 30 minuti tramite migrazione; ogni modifica successiva può aggiornare la durata e l'evento collegato. Il 29 luglio il flusso ha superato i test automatici e il controllo dell'admin a 1440×900 e 390×844 px; durante il collaudo è stata corretta anche la precedenza CSS che nascondeva le card appuntamento su mobile.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/modifica_appuntamento.html`, `migrations/versions/4d8b2c7a91e6_durata_effettiva_appuntamento.py`, `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `ROADMAP.md`.

## D-063 — Revoca Analytics effettiva

- Data: 2026-07-29.
- Stato: implementata; validazione legale ancora necessaria.
- Decisione: non caricare GA4 prima dell'accettazione esplicita. Una scelta rifiutata o revocata deve impostare a `denied` le categorie Analytics e Ads, impedire nuovi eventi di conversione e far scadere soltanto i cookie riconducibili a Google Analytics. La presenza di `window.gtag` non equivale al consenso: ogni evento di conversione verifica anche la scelta salvata.
- Motivo: la revoca deve produrre un effetto tecnico immediato nella pagina corrente e non soltanto impedire il caricamento nelle visite successive.
- Conseguenze: `GOOGLE_ANALYTICS_ID` resta assente dagli ambienti operativi fino alla validazione professionale; la suite JavaScript verifica assenza di richieste prima del consenso, accettazione, rifiuto, valori salvati non validi, revoca e conservazione dei cookie non Analytics.
- Collegamenti: `static/js/analytics-consent.js`, `static/js/conversion-tracking.js`, `tests/js/analytics-consent.test.js`, `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `ROADMAP.md`.

## D-064 — Staging stabile su main con deploy manuali

- Data: 2026-07-29.
- Stato: implementata nel codice e applicata al Web Service il 2026-07-30; il collegamento del Blueprint è stato poi revocato dalla D-066.
- Decisione: fare seguire al Blueprint e al Web Service di staging il branch `main`, mantenendo `autoDeployTrigger` disattivato. Il branch identifica la linea stabile del progetto; il commit effettivamente distribuito continua a essere scelto e verificato prima di ogni deploy manuale.
- Motivo: i branch di lavorazione precedenti non devono restare configurazione permanente dell'ambiente condiviso e non devono creare divergenza tra pannello Render e Blueprint.
- Conseguenze: al momento dell'allineamento Blueprint e Web Service puntavano a `main`, con Auto Sync e auto-deploy disattivati. L'approvazione della modifica di branch nel Blueprint avviò comunque un deploy del commit `e4fea38`; l'esecuzione fu annullata e il deploy live rimase `8a4ad84`. Le sincronizzazioni Blueprint vanno quindi trattate come operazioni capaci di avviare un deploy anche quando i nuovi commit non lo fanno automaticamente. L'allineamento non modificò piani, dominio, integrazioni o segreti. Lo stato successivo è quello della D-066: Blueprint disconnesso, Web Service ancora su `main`.
- Collegamenti: `render.yaml`, `OPERATIONS.md`, `ROADMAP.md`.

## D-065 — L'ultima disponibilità può accogliere una coppia

- Data: 2026-07-29.
- Stato: sostituita e precisata da D-072.
- Decisione: per i corsi individuali una richiesta di coppia occupa due posti ma resta accettabile quando, al momento dell'invio, il corso ha ancora un solo posto disponibile. Dopo il salvataggio la data non accetta altre richieste. Le iscrizioni annullate non occupano posti e possono rendere nuovamente disponibile la data.
- Motivo: l'eccezione sull'ultimo posto è una scelta operativa esplicita dell'attività, non un errore di capienza da bloccare automaticamente.
- Conseguenze: la contestazione sul limite inderogabile non è più valida nei termini formulati: 14 è la capienza nominale tipica e 15 è l’esito massimo dell’iscrizione automatica in quel caso, non un divieto assoluto per l’operatore. La regola completa e la lista d’attesa sono disciplinate da D-072.
- Collegamenti: `app.py`, `tests/test_app.py`, `SITE_MAP_AND_FLOWS.md`, `ROADMAP.md`.

## D-066 — Revoca del Sync Hook tramite disconnessione del Blueprint

- Data: 2026-07-30.
- Stato: approvata dall'attività e implementata.
- Decisione: disconnettere il Blueprint dello staging dopo che il relativo Sync Hook è stato visualizzato durante un controllo operativo e non può più essere considerato affidabile. Mantenere Web Service e PostgreSQL esistenti, senza ricollegare il Blueprint fino a una finestra di deploy controllata.
- Motivo: Render non espone una rotazione isolata del Sync Hook; la disconnessione ne revoca l'uso senza eliminare le risorse gestite.
- Conseguenze: al termine della disconnessione lo staging non era più gestito dal Blueprint, il Web Service restava collegato a `main`, il database era intatto e il deploy live era ancora `8a4ad84`. La disconnessione non avviò deploy e il controllo immediatamente successivo di `/healthz` restituì `200`. Nella stessa giornata il database fu poi migrato e il deploy manuale `148ec36` riallineò codice e schema, come registrato in `OPERATIONS.md` e `ROADMAP.md`. Il futuro ricollegamento deve verificare il piano proposto e considerare la prima sincronizzazione capace di avviare un deploy.
- Collegamenti: `render.yaml`, `OPERATIONS.md`, `ROADMAP.md`.

## D-067 — Google Calendar API unica per lettura e scrittura

- Data: 2026-07-30.
- Stato: approvata dall'attività, implementata e verificata con un test reale controllato; configurazione nell'ambiente Render autorizzato e prove end-to-end ancora da completare.
- Decisione: usare un unico account di servizio e Google Calendar API per leggere gli impegni sincronizzati da Arzamed e per creare, modificare o cancellare gli eventi del sito. Eliminare l'URL iCal dalla configurazione.
- Motivo: il calendario Google operativo è già il collante bidirezionale con Arzamed e la scrittura richiede comunque un'identità API. Usare la stessa integrazione anche in lettura riduce segreti e percorsi di errore duplicati.
- Conseguenze: l'account Google dello studio resta proprietario del calendario; l'app usa un'identità tecnica separata con accesso limitato agli eventi del solo calendario operativo. La lettura API espande le ricorrenze, conserva una cache per giorno e riusa la copia scaduta in caso di errore. Il 30 luglio 2026 sono stati verificati progetto Cloud, API, identità tecnica, chiave e condivisione del calendario con permesso di modifica degli eventi. Un test reale controllato ha completato autenticazione, lettura, creazione, rilettura e cancellazione immediata di un evento sintetico. Il JSON resta escluso da Git e non documentato; mancano ancora l'inserimento sicuro nell'ambiente Render autorizzato e il collaudo completo dei flussi con Calendar ed email reali.
- Collegamenti: `app.py`, `config.py`, `render.production.yaml`, `OPERATIONS.md`, `ROADMAP.md`.

## D-068 — La casella Zimbra riceve gli avvisi amministrativi

- Data: 2026-07-30.
- Stato: approvata dall'attività; da configurare nella preproduzione privata.
- Decisione: usare `info@scstudioinfermieristico.it` come valore di `MAIL_ADMIN_RECIPIENT`, oltre che come casella mittente approvata.
- Motivo: le notifiche operative del sito devono arrivare nella casella ufficiale già presidiata e collaudata, senza introdurre un secondo indirizzo o inoltri non necessari.
- Conseguenze: nuove prenotazioni, richieste di call, iscrizioni e ricontatti inviano l'avviso interno alla casella Zimbra dello studio. Il valore viene inserito soltanto nell'ambiente autorizzato; non abilita invii nello staging gratuito e non modifica `MAIL_SUPPRESS_SEND`.
- Collegamenti: `OPERATIONS.md`, `config.py`, `app.py`, `render.production.yaml`.

## D-069 — Sistema permanente per la produzione social

- Data: 2026-08-03.
- Stato: approvata dall'attività e documentata.
- Decisione: separare le regole permanenti per i contenuti Instagram e TikTok dai pacchetti settimanali. Il sistema generale disciplina ruoli, stati, fonti, approvazioni, registrazione, montaggio, consegne e misurazione. Ogni cartella settimanale contiene temi, script, CTA, calendario e scelte specifiche.
- Motivo: permettere al creator di riprendere il lavoro senza ricostruire ogni volta il metodo e senza confondere decisioni valide per una settimana con regole durevoli.
- Conseguenze: le nuove settimane partono da un template comune, mantengono un registro delle fonti e vengono riviste a 7 e 30 giorni. Il pacchetto settimanale può derogare al sistema solo in modo esplicito e approvato.
- Collegamenti: `MARKETING_PLAN.md`, `CONTENT_AND_ASSETS.md`, `reels-creator-system/README.md`, `reels-2026-08-03/README.md`.

## D-070 — I tre post fissati occupano gli slot editoriali ordinari

- Data: 2026-08-03.
- Stato: approvata.
- Decisione: distribuire i tre post destinati al fissaggio in tre normali slot editoriali prima del lancio: **Inizia da qui** nella settimana 10-16 agosto, **Corsi pratici a Montesilvano** nella settimana 17-23 agosto e **Consulenza sonno 0-12 mesi online** nella settimana 24-30 agosto. Il 3 settembre si controllano e si fissano definitivamente i tre post. Ciascuno sostituisce il carosello o la fotografia editoriale della settimana e non si aggiunge alla frequenza prevista.
- Motivo: preparare il profilo senza introdurre un quarto contenuto settimanale e senza concentrare tre pubblicazioni istituzionali nello stesso periodo.
- Conseguenze: nelle tre settimane la cadenza resta di due video più il post strategico; il piano marketing registra date e controllo finale, mentre il sistema del creator applica la stessa regola ai calendari futuri.
- Collegamenti: `MARKETING_PLAN.md`, `reels-creator-system/README.md`.

## D-071 — Gli stati esterni sono evidenze datate, non verità correnti

- Data: 2026-08-13.
- Stato: approvata come regola di governo documentale.
- Decisione: ogni affermazione sullo stato esterno di Render, dominio, email, Calendar, profili social, pubblicazioni e piattaforme deve indicare data ed evidenza del controllo. Una verifica storica non prova lo stato corrente; il repository può confermare codice e configurazione dichiarativa, non ciò che è live nei pannelli esterni.
- Motivo: l'audit ha trovato decisioni corrette al momento della registrazione ma formulate come stato presente anche dopo verifiche successive, in particolare i riferimenti al deploy `8a4ad84`, alla configurazione Calendar ancora assente e ai contenuti social soltanto programmati.
- Conseguenze: prima di deploy, apertura pubblica, attivazione di integrazioni o campagna si riconciliano in sola lettura commit live, piano, variabili non sensibili, dominio e ultimo esito disponibile. Uno stato `Programmato` rimasto oltre l'orario previsto diventa `da verificare`, non `Pubblicato`. `ROADMAP.md` distingue la data della revisione documentale dalla data dell'ultima evidenza esterna.
- Collegamenti: `ROADMAP.md`, `OPERATIONS.md`, `CONTENT_AND_ASSETS.md`, `MARKETING_PLAN.md`.

## D-072 — Capienza online, lista d’attesa e deroga amministrativa

- Data: 2026-08-13.
- Stato: approvata e implementata localmente; collaudo end-to-end ancora richiesto.
- Decisione: ogni edizione ha una capienza nominale configurabile. Il sito accetta una richiesta soltanto se, prima dell’invio, i posti occupati sono inferiori alla capienza nominale; una coppia può occupare l’ultimo posto nominale e portare il totale a `capienza + 1`. Raggiunta la capienza nominale, nuove richieste entrano in lista d’attesa. L’admin può sempre superare il limite online, ma deve confermare l’eccezione e registrarne il motivo.
- Motivo: con capienza nominale 14, a 13 adesioni deve restare possibile accettare sia un singolo, arrivando a 14, sia una coppia, arrivando a 15. Il valore 15 limita il flusso automatico del sito in quel caso; non rappresenta un limite fisico inderogabile per l’inserimento manuale.
- Conseguenze: la prima persona in lista d’attesa riceve automaticamente un invito valido 24 ore quando si libera capienza. Le richieste in lista o invitate non occupano posti finché l’invito non viene accettato. L’admin conserva il motivo di ogni superamento del limite online.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/accetta_lista_attesa.html`, `tests/test_app.py`, D-065.

## D-073 — L’area admin è una regia operativa a account singolo

- Data: 2026-08-13.
- Stato: approvata e implementata localmente; collaudo mobile e integrazioni reali ancora richiesti.
- Decisione: organizzare l’admin in Agenda, Richieste, Corsi, Persone, Attività, Errori e Impostazioni. La vista iniziale è l’agenda giornaliera con accesso alla settimana. Tutte le richieste aperte hanno prossima azione e scadenza; quelle scadute restano bloccanti, diventano urgenti e generano un promemoria. Il lancio usa un solo account, sessione inattiva di 60 minuti e tracciamento append-only delle modifiche.
- Motivo: il pannello precedente separava i dati per modulo ma non sosteneva il lavoro quotidiano, la riconciliazione degli errori o il passaggio da richiesta a appuntamento/iscrizione.
- Conseguenze: l’admin crea appuntamenti in stato `In attesa`, pause e chiusure; propone slot con link di accettazione; gestisce stati, note, attività, corsi duplicabili o unificabili, spostamenti, export CSV/PDF e incontri del percorso nascita. Telefono ed email segnalano possibili duplicati ma non uniscono automaticamente; il codice fiscale unisce le persone dei corsi e le altre pratiche vengono collegate manualmente. Multiaccount, ruoli e assegnazioni restano fuori dal lancio.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `static/css/admin.css`, `migrations/versions/a13d8f7c2b40_strumenti_operativi_area_admin.py`.

## D-074 — `scstudioinfermieristico.it` è il dominio definitivo

- Data: 2026-08-13.
- Stato: approvata.
- Decisione: chiudere come fallita la trattativa per `studioinfermieristico.it` e mantenere `scstudioinfermieristico.it`, già acquistato e controllato dall’attività, come dominio definitivo.
- Motivo: la trattativa non ha prodotto l’acquisizione e non deve più condizionare canonical, configurazione, materiali o calendario di lancio.
- Conseguenze: non esiste più una biforcazione sul dominio principale. Il collegamento DNS e l’apertura pubblica restano azioni esterne soggette ai gate di pre-lancio; questa decisione non prova che il dominio sia già collegato al servizio live.
- Collegamenti: D-027, `OPERATIONS.md`, `ROADMAP.md`.

## D-075 — TikTok sospeso fino a nuova decisione

- Data: 2026-08-13.
- Stato: approvata.
- Decisione: accantonare pubblicazione, adattamenti e misurazione su TikTok fino a data da destinarsi. Instagram resta il canale social operativo; i file TikTok esistenti restano materiale storico, non attività programmata.
- Motivo: evitare che calendari superati e consegne non verificate continuino a essere interpretati come impegni correnti.
- Conseguenze: checklist e piani non devono trattare TikTok come gate di lancio. La riattivazione richiederà una nuova decisione esplicita e un calendario aggiornato.
- Collegamenti: D-069, `MARKETING_PLAN.md`, `CONTENT_AND_ASSETS.md`, `reels-creator-system/README.md`.

## D-076 — Vista mensile, richieste organizzative e quiz entrano nel perimetro di lancio

- Data: 2026-08-13.
- Stato: approvata e implementata localmente; collaudo visuale e integrazioni reali ancora richiesti.
- Decisione: anticipare dal post-lancio tre estensioni. L’admin offre una vista mensile compatta con accesso al dettaglio giornaliero. Aziende e gruppi usano un modulo pubblico e una coda dedicati, con conferma di ricezione, attività generate dai passaggi di stato, proposta email tracciata e conversione in corso riservato. Il quiz `Da dove parto?` orienta verso flussi pubblici già approvati senza inviare o conservare risposte.
- Motivo: queste funzioni riducono tre attriti già visibili prima del lancio: lettura del carico su più settimane, gestione impropria delle richieste organizzative nel modulo individuale e difficoltà di scelta fra offerte diverse.
- Conseguenze: i corsi generati da una richiesta organizzativa hanno stato `Chiuso`, compaiono nell’agenda e in Google Calendar ma non tra le date pubbliche. La richiesta aziendale non conferma disponibilità, data o preventivo. Il quiz non formula diagnosi, non raccoglie dati sanitari e lascia sempre visibili tutte le alternative. Multiaccount, ruoli e pagamenti restano esclusi.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `templates/richiesta_azienda.html`, `templates/da_dove_parto.html`, `migrations/versions/c84f2d1a9e70_richieste_aziende_e_gruppi.py`, `ROADMAP.md`.


## D-077 — L’admin può creare appuntamenti con contatti incompleti

- Data: 2026-08-13.
- Stato: approvata e implementata localmente; collaudo visuale ancora richiesto.
- Decisione: nella creazione manuale di un appuntamento, telefono ed email sono facoltativi. Se uno o entrambi mancano, l’admin chiede una conferma esplicita prima del salvataggio e registra nell’audit i contatti assenti. Un valore compilato ma non valido resta bloccante. Nome, prestazione, data, ora e durata restano obbligatori.
- Motivo: l’operatore può conoscere l’impegno prima di disporre di tutti i recapiti; rifiutare l’inserimento o svuotare il modulo crea perdita di lavoro senza aumentare l’affidabilità del dato.
- Conseguenze: il modulo conserva i valori quando il server rileva un errore, usa il calendario nativo per la data e menu distinti per ore e minuti con granularità di cinque minuti. I contatti mancanti possono essere integrati successivamente dalla scheda della pratica.
- Collegamenti: `app.py`, `templates/admin.html`, `static/js/admin-azioni.js`, `static/css/admin.css`, `tests/test_app.py`.

## D-078 — L’agenda admin si apre sulla vista mensile

- Data: 2026-08-16.
- Stato: approvata dall’attività e implementata.
- Decisione: aprire `/admin` sulla vista mensile e ordinare i controlli dell’agenda come `Mese`, `Settimana`, `Giorno`. Le viste settimanale e giornaliera restano disponibili tramite parametro esplicito.
- Motivo: offrire all’accesso una lettura immediata del carico complessivo e rendere l’ordine dei controlli coerente con la vista iniziale.
- Conseguenze: questa decisione sostituisce D-073 soltanto nel punto in cui indicava l’agenda giornaliera come vista iniziale. Un valore `vista` assente o non valido apre il mese corrente; gli strumenti operativi esclusi dalla griglia mensile restano disponibili nelle viste settimana e giorno.
- Collegamenti: `app.py`, `templates/admin.html`, `tests/test_app.py`, D-073, D-076.

## D-079 — Le risorse definitive iniziano come preproduzione privata pagata

- Data: 2026-08-23.
- Stato: approvata e implementata.
- Decisione: creare dal Blueprint dedicato un Web Service Starter e un PostgreSQL Basic-256mb da 1 GB in Francoforte, per un costo previsto di 13,30 USD al mese più eventuali imposte, mantenendoli come preproduzione privata con `APP_ENV=staging`, Basic Auth, `noindex`, invii soppressi, integrazioni reali disattivate e nessun dominio personalizzato.
- Motivo: i collaudi SMTP, Calendar e dei flussi end-to-end richiedono risorse separate e a pagamento, ma non giustificano l'apertura pubblica o il cutover di produzione prima della chiusura dei P0.
- Conseguenze: il database gratuito non viene promosso né copiato; Auto Sync e auto-deploy restano disattivati. Dopo il primo accesso amministrativo le variabili `ADMIN_BOOTSTRAP_*` vengono rimosse dal pannello e dal Blueprint, mentre l'account resta nel database. Finché `STAGING_LIVE_INTEGRATIONS=false`, il software non deve autenticare, leggere o scrivere su Google Calendar. Secret file Google, integrazioni reali, backup esterno, deploy successivi, `APP_ENV=production`, DNS e dominio conservano gate distinti.
- Collegamenti: `render.production.yaml`, `OPERATIONS.md`, `ROADMAP.md`, D-030, D-061, D-071.

## D-080 — Google Calendar è una dipendenza degradabile e non condivide trasporti HTTP

- Data: 2026-08-25.
- Stato: approvata e implementata localmente; deploy e nuovo collaudo in preproduzione richiesti.
- Decisione: ogni operazione Google Calendar usa un proprio trasporto HTTP autenticato con timeout breve. Le letture della stessa giornata usano uno snapshot unico, una cache sincronizzata e un solo tentativo concorrente; dopo un errore un circuito breve evita raffiche verso Google e ammette un fallback stale limitato. Le richieste web non eseguono retry sincroni prolungati.
- Motivo: il collaudo con Calendar ID non valido e accessi concorrenti ha causato un crash nativo del worker Gunicorn, perdita dell'health check e `502`. Ridurre soltanto i thread avrebbe nascosto la condivisione non sicura senza rendere Calendar una dipendenza realmente degradabile.
- Conseguenze: un errore Calendar non annulla il dato locale e viene registrato in `RegistroEvento`; il sito e `/healthz` devono restare disponibili. La disponibilità locale durante il circuito non dimostra che Arzamed sia libero. La produzione resta bloccata finché il test concorrente controllato non esclude crash e riavvii dell'istanza.
- Collegamenti: `app.py`, `config.py`, `tests/test_app.py`, `OPERATIONS.md`, `ROADMAP.md`, D-071, D-079.

## D-081 — Le sincronizzazioni Calendar fallite vengono ritentate automaticamente

- Data: 2026-08-25.
- Stato: approvata e implementata localmente; deploy e collaudo reale richiesti.
- Decisione: prima della riconciliazione oraria, il sistema riprova automaticamente le pratiche attive con sincronizzazione `da_sincronizzare`, `errore` o `mancante`. Il ciclo invia all’indirizzo amministrativo una sola email riepilogativa di successo, fallimento o esito parziale quando esiste almeno un tentativo. Gli stati `difforme` ed `eliminato_esternamente` restano esclusi dal retry e richiedono una scelta esplicita dell’operatore.
- Motivo: il dato locale sopravvive già a un guasto Calendar, ma un evento mai creato non deve restare disallineato fino a un intervento manuale dopo il ripristino della dipendenza.
- Conseguenze: il recupero automatico avviene al primo ciclo orario utile, non istantaneamente. Prima di creare un evento privo di `google_event_id`, il retry cerca su Calendar le proprietà private `studioEntity` e `studioEntityId`: se trova una corrispondenza la ricollega e la aggiorna, evitando duplicati quando un precedente `insert` era riuscito ma la risposta era andata persa. Più corrispondenze bloccano il recupero automatico. Dopo il successo gli errori Calendar aperti della pratica vengono chiusi conservandone lo storico; un fallimento resta visibile e viene ritentato nel ciclo successivo senza annullare il dato locale.
- Collegamenti: `app.py`, `tests/test_app.py`, `OPERATIONS.md`, `ROADMAP.md`, D-073, D-080.

## D-082 — Le modifiche umane su Calendar richiedono una decisione prioritaria

- Data: 2026-08-26.
- Stato: approvata, implementata e verificata localmente; deploy e collaudo reale ancora richiesti.
- Decisione: trattare sia `404/410` sia `status="cancelled"` come `eliminato_esternamente`. Gli stati `difforme` ed `eliminato_esternamente` non entrano nell’autoretry e aprono un avviso prioritario al primo ingresso utile nell’admin. L’ingresso esegue una riconciliazione rapida soltanto se il controllo precedente non è abbastanza recente; timeout, circuito e fallback di D-080 restano applicati e l’admin non viene bloccato da Google. `Decidi dopo` nasconde il modal per i soli conflitti già visti nella sessione, lasciando banner, stato e anomalia aperti.
- Motivo: una modifica o cancellazione manuale può essere intenzionale e non può essere interpretata come guasto tecnico. Ricreare automaticamente l’evento o chiudere l’anomalia senza scelta potrebbe contraddire una decisione sanitaria e nascondere il disallineamento.
- Conseguenze: una modifica temporale di appuntamento o call può essere applicata al database soltanto dopo un nuovo controllo di disponibilità, audit ed email di spostamento; i titoli non vengono interpretati per ricavare dati sanitari o anagrafici. La conferma dei dati del sito riscrive Calendar. Un evento eliminato può essere ricreato con un nuovo ID senza nuova email oppure portare all’annullamento tramite il normale workflow con email. Il comando generico `Segna risolto` e la sincronizzazione in blocco sono vietati per questi due stati. Il 26 agosto il modal è stato verificato con dati sintetici a 1440×900 e 390×844 px: nessun overflow di pagina, confronto completo, azioni da almeno 44 px, `Decidi dopo` persistente nella sessione e riproposizione dopo un nuovo login.
- Collegamenti: `app.py`, `config.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `static/css/admin.css`, `static/js/admin-azioni.js`, `tests/test_app.py`, `SITE_MAP_AND_FLOWS.md`, `OPERATIONS.md`, `ROADMAP.md`, D-073, D-080, D-081.

## D-083 — Gli istanti operativi sono UTC e l’admin li mostra nel fuso italiano

- Data: 2026-08-26.
- Stato: approvata e implementata localmente; verifica dopo il deploy richiesta.
- Decisione: salvare i nuovi timestamp tecnici e di audit come UTC senza offset nelle colonne `DateTime` esistenti e convertirli in `Europe/Rome` soltanto in visualizzazione. I log admin mostrano anche `CET` o `CEST`; date e orari civili di appuntamenti, corsi e attività restano nel fuso italiano.
- Motivo: il server registrava `datetime.now()` nel proprio fuso UTC e l’admin stampava il valore senza conversione, mostrando due ore in meno durante l’ora legale. Salvare ore locali senza offset renderebbe inoltre ambigua l’ora ripetuta al ritorno all’ora solare.
- Conseguenze: i timestamp storici già prodotti dal servizio Render vengono interpretati come UTC e appaiono corretti senza migrazione o riscrittura distruttiva. `ZoneInfo` applica le regole CET/CEST; i test coprono il salto primaverile, le due diverse 02:30 autunnali e il rendering admin. Le scadenze relative e i confronti tecnici usano UTC, mentre le regole del calendario operativo usano la data locale italiana.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `templates/admin_questionario_sonno.html`, `templates/accetta_lista_attesa.html`, `tests/test_app.py`, `OPERATIONS.md`, `ROADMAP.md`.

## D-084 — Il collaudo reale chiude integrazioni, prestazioni e resilienza condivisa

- Data: 2026-08-26.
- Stato: approvata e verificata nella preproduzione privata.
- Decisione: considerare superato il blocco P0 relativo a SMTP reale, Google Calendar, flusso delle prestazioni sanitarie e resilienza delle integrazioni condivise, sulla base del collaudo controllato svolto dal 24 al 26 agosto 2026 con dati sintetici. In `ROADMAP.md` gli step 8, 9 e 13 passano a `Completato`.
- Motivo: la prova ha verificato consegna e tracciamento delle email, salvataggio locale durante un guasto SMTP, creazione, modifica e cancellazione Calendar senza duplicati, fuso `Europe/Rome`, rilevazione e decisione su modifiche o cancellazioni esterne, recupero automatico dopo indisponibilità e conservazione del dato principale. La build precedente aveva prodotto un `502`, errori TLS e crash del worker con code 139; dopo D-080, D-081 e D-082 il medesimo perimetro è stato riprovato con esito positivo e autoretry reale `1/1` riuscito.
- Conseguenze: le richieste di deploy e collaudo reale ancora indicate negli stati storici di D-080, D-081 e D-082 risultano chiuse da questa evidenza, senza rimuovere la traccia del fallimento iniziale. Tutti gli appuntamenti sintetici sono stati eliminati; log tecnici e audit possono restare come evidenza. Questo esito non completa i flussi specifici di corsi o consulenza sonno, non valida privacy, testi legali, GA4, dominio o campagna e non autorizza `APP_ENV=production`, rimozione di Basic Auth/`noindex`, DNS o apertura pubblica. La verifica post-deploy del timestamp admin prevista da D-083 resta separata.
- Collegamenti: `OPERATIONS.md`, `ROADMAP.md`, D-071, D-079, D-080, D-081, D-082, D-083.

## D-085 — Admin e directory corsi mostrano il contesto operativo

- Data: 2026-08-27.
- Stato: approvata, implementata e verificata localmente a 1440×900 e 390×844 px.
- Decisione: distinguere nella scheda appuntamento lo stato della pratica dallo stato Google Calendar; mostrare nei log e negli errori il nome della persona, del corso o dell’attività accanto all’ID; separare nell’admin la creazione di una nuova edizione dalla gestione corsi e proporre `S.C. Studio Infermieristico` come luogo iniziale modificabile. Nel sito pubblico il quiz `Da dove parto?` riceve un richiamo dedicato nell’header, la CTA della disostruzione diventa `Iscriviti ora` e la directory corsi apre con tutte le edizioni pubbliche future già organizzate, collegate al modulo con data preselezionata.
- Motivo: stati e identificativi privi di contesto rallentano la gestione quotidiana; nello stesso modo, una panoramica per sole tipologie obbliga chi arriva dalla homepage a cercare di nuovo una data già pubblicata.
- Conseguenze: non cambia lo schema dati. I riferimenti dei log vengono risolti al momento della visualizzazione e, se la pratica non esiste più, resta disponibile l’ID storico. La lista pubblica include edizioni future `Aperto` o `Completo`, esclude corsi privati, annullati o archiviati e preseleziona soltanto date ancora aperte. Il collaudo con dati sintetici ha verificato assenza di overflow, leggibilità del richiamo quiz, lista edizioni, pannello nuovo corso, riferimenti negli errori ed etichette di stato appuntamento/Calendar.
- Collegamenti: `app.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `templates/base.html`, `templates/iscrizione_corsi.html`, `templates/iscrizione_corso.html`, `static/css/admin.css`, `static/css/base.css`, `static/css/internal-pages.css`, `static/js/admin-azioni.js`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `tests/test_app.py`.

## D-086 — L’etichetta dell’edizione corso è un dato descrittivo esteso

- Data: 2026-08-27.
- Stato: approvata e implementata localmente; deploy della migrazione e ripetizione del collaudo PostgreSQL richiesti.
- Decisione: portare `iscrizione_corso.data_corso` da `VARCHAR(20)` a `VARCHAR(255)` nel modello e tramite la revisione Alembic `e2f4a6b8c901`. Rendere inoltre la sticky bar di `base.html` indipendente dal contesto della pagina originaria: quando una pagina 500 deriva da `iscrizione_corso` ma non dispone della variabile `corso`, la barra viene disattivata.
- Motivo: `data_corso` conserva un’etichetta leggibile composta da data, ora e luogo, oltre a valori come `Da ricontattare per prossime date` e `Percorso di 9 incontri`; il limite di 20 caratteri causava `StringDataRightTruncation` al primo inserimento reale su PostgreSQL. Durante lo stesso errore, il template 500 tentava di leggere `corso.has_open_dates` e generava un secondo errore Jinja.
- Conseguenze: l’upgrade amplia la colonna senza trasformare né troncare i valori esistenti. Il downgrade a 20 caratteri non è sicuro dopo il salvataggio di etichette più lunghe e può richiedere una bonifica esplicita dei dati. Prima di riprendere il collaudo corsi bisogna distribuire il codice, applicare `flask db upgrade`, confermare la revisione `e2f4a6b8c901` con `flask db check` e ripetere l’iscrizione singola che aveva prodotto HTTP 500.
- Collegamenti: `app.py`, `templates/base.html`, `migrations/versions/e2f4a6b8c901_estende_data_corso.py`, `tests/test_app.py`, `tests/test_migrations.py`, `OPERATIONS.md`, `ROADMAP.md`, D-085.

## D-087 — Data, luogo e interesse restano azioni distinte nel modulo corsi

- Data: 2026-08-27.
- Stato: approvata, implementata e verificata localmente a 1440×900 e 390×844 px.
- Decisione: mostrare nelle iscrizioni data e ora come unica scelta modificabile e il luogo dell’edizione in un campo separato di sola lettura, aggiornato in base alla data. Quando le date aperte non sono compatibili con le esigenze della persona, presentare sotto i dati dell’edizione un’azione separata `Lascia il tuo interesse`, diretta al modulo minimo di ricontatto con la tematica già preselezionata.
- Motivo: il luogo è una proprietà dell’edizione e non una preferenza dell’iscritto; inserirlo nell’etichetta della data rendeva meno leggibili entrambi i dati. `Nessuna data compatibile` non è una data e non deve apparire nello stesso menu: confonderebbe una richiesta di ricontatto con un’iscrizione e richiederebbe dati amministrativi non necessari.
- Conseguenze: il valore descrittivo completo continua a essere salvato in `iscrizione_corso.data_corso`, quindi email e admin conservano data, ora e luogo. La richiesta d’interesse usa il flusso già minimizzato, non occupa posti e può essere inviata anche quando esistono altre date aperte. Il collaudo responsive ha verificato aggiornamento del luogo, tematica preselezionata, assenza del codice fiscale nel ricontatto e assenza di overflow. Non cambia lo schema dati.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `app.py`, `templates/iscrizione_corso.html`, `templates/interesse_corsi.html`, `templates/base.html`, `static/css/components.css`, `static/js/course-registration.js`, `tests/test_app.py`, `tests/js/course-registration.test.js`, D-057, D-086.

## D-088 — La mail al partecipante segue la decisione amministrativa sul posto

- Data: 2026-08-27.
- Stato: approvata, implementata e verificata localmente.
- Decisione: all’invio di un modulo corso, compreso il percorso nascita privato, salvare una richiesta `Nuova` e inviare soltanto l’alert Zimbra allo studio. La pagina di esito dichiara che il posto non è confermato. La mail al partecipante parte sul primo passaggio admin a `Confermato`; annullamento e spostamento individuale inviano le rispettive comunicazioni.
- Motivo: una ricevuta automatica immediata può essere interpretata come conferma del posto prima della verifica dello studio. Stato gestionale e comunicazione devono coincidere, senza duplicare messaggi quando l’admin seleziona nuovamente lo stesso stato.
- Conseguenze: le richieste collegate a una data richiedono l’email; i ricontatti senza data mantengono email facoltativa e flusso minimo. Stato o spostamento vengono persistiti prima di SMTP; un errore di invio non annulla l’operazione ed è registrato in `EmailOperativa` e `RegistroEvento`. Le iscrizioni inserite manualmente già come `Confermato` inviano la stessa mail. Le pagine di conferma pubblica e privata sono state controllate a 1440 x 900 e 390 x 844 px senza overflow; la suite locale passa con 225 test Python e 33 test JavaScript. Non cambia lo schema dati.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `OPERATIONS.md`, `ROADMAP.md`, `app.py`, `templates/iscrizione_corso.html`, `templates/conferma_iscrizione_corso.html`, `templates/conferma_iscrizione_accompagnamento.html`, `templates/admin.html`, `templates/admin_dettaglio.html`, `static/css/components.css`, `tests/test_app.py`, D-057, D-087.

## D-089 — La gestione di un’edizione parte dagli iscritti e gli errori restano nel modulo

- Data: 2026-08-27.
- Stato: approvata, implementata e verificata localmente a 1440×900 e 390×844 px.
- Decisione: aprire i corsi dall’agenda e dalla panoramica direttamente sulla scheda dell’edizione, con la lista dei partecipanti come prima sezione operativa. Nei moduli corso, mostrare l’errore dentro il modulo, portare focus e scroll sul campo evidenziato e conservare i dati inseriti. Per la disostruzione, mostrare i dati del secondo partecipante soltanto con `Coppia`, rendendo obbligatorio il nome e facoltativo il codice fiscale. Il dettaglio del calendario homepage dispone di un comando esplicito di chiusura che restituisce il focus al giorno selezionato.
- Motivo: l’azione più frequente su un corso già programmato è verificare chi partecipa; filtri intermedi, ritorno in cima e campi condizionali sempre visibili rallentano rispettivamente l’operatore e la persona che compila.
- Conseguenze: il collegamento storico `/admin?corso_id=<id>#admin-corsi` continua a filtrare la tabella, ma `Vedi iscritti` e gli eventi agenda usano `/admin/pratica/Corso/<id>#partecipanti-corso`. Il server ignora eventuali dati del secondo partecipante inviati per una partecipazione singola. Il controllo responsive ha verificato lista partecipanti, campi coppia, chiusura del calendario con ritorno del focus ed errore telefono evidenziato senza overflow; la suite passa con 227 test Python e 35 test JavaScript. Non cambia lo schema dati.
- Collegamenti: `SITE_MAP_AND_FLOWS.md`, `CONTENT_AND_ASSETS.md`, `ROADMAP.md`, `app.py`, `templates/admin.html`, `templates/admin_dettaglio.html`, `templates/homepage.html`, `templates/iscrizione_corso.html`, `static/css/admin.css`, `static/css/components.css`, `static/js/calendario.js`, `static/js/course-registration.js`, `tests/test_app.py`, `tests/js/course-registration.test.js`, D-073, D-078, D-087.

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
