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

- Stato: approvata per la fase pilota.
- Decisione: consulenza mirata da 75 € per un solo problema circoscritto; percorso personalizzato da 180 € come offerta principale quando più fattori si influenzano.
- Motivo: offrire una soglia d'ingresso senza svalutare il percorso completo.
- Da verificare: domanda nazionale, appropriatezza e disponibilità a pagare.

## D-005 — Call gratuita prima del pagamento

- Stato: approvata.
- Decisione: call conoscitiva gratuita di circa 15 minuti prima di proporre o far pagare una consulenza.
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

- Stato: approvata.
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
