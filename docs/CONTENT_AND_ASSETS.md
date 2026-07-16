# Contenuti e materiali

Ultimo aggiornamento: 16 luglio 2026.

## Scopo

Questo documento registra testi, immagini e materiali disponibili. Non sostituisce i template: serve a distinguere ciò che è approvato, provvisorio o ancora da selezionare.

## Messaggi approvati

- Sintesi identitaria: `Competenza sanitaria, parole semplici`.
- Promessa homepage approvata: `Nei primi mesi non servono risposte perfette. Serve capire cosa osservare e cosa fare.`
- Introduzione ai pilastri della homepage: `Partite da ciò che serve oggi alla vostra famiglia.`
- Percezione desiderata: Selene è una professionista sanitaria competente e vicina, non un brand impersonale.
- Corsi: apprendimento pratico, segnali da osservare, gesti da allenare e date disponibili.
- Sonno: comprensione della situazione familiare e percorso non rigido, senza risultati garantiti.
- Corso nascita: visione a 360 gradi con infermiera, ostetrica, psicologa, osteopata e nutrizionista.
- BLSD: investimento concreto nella sicurezza degli ambienti.
- Instagram in homepage: attività reali e vita dello studio come prova secondaria, senza sostituire le CTA dei due pilastri.
- Prestazioni infermieristiche: la sezione `Dove ci troviamo` indica Via Carmine D'Agnese 43, 65015 Montesilvano (PE), con mappa e collegamento a Google Maps.

## Naming approvato

| Contenuto | Forma da usare |
|---|---|
| Sede/brand | S.C. Studio Infermieristico |
| Professionista | Selene Campetta |
| Landing attuale | Consulenza del sonno / Consulenza sonno |
| Formula breve | Consulenza mirata |
| Formula principale | Percorso sonno personalizzato |
| Percorso nascita | Corso di accompagnamento alla nascita |
| Corso pediatrico | Disostruzione pediatrica e tagli sicuri |
| Rianimazione | BLSD, accompagnato da una spiegazione concreta |

`Consulenze genitori` è un possibile contenitore futuro, non il nome della landing sonno attuale. Non usare `SOS neomamma` come naming principale.

## CTA approvate

- `Scopri i corsi`
- `Richiedi la call gratuita`
- `Prenota`
- `Iscrizione individuale`
- `Richiedi il corso in studio o in azienda`

Usare `Scrivimi` solo quando non esiste un'azione più specifica. WhatsApp non deve sostituire automaticamente moduli e flussi dedicati.

## Microtesti dell'header

- I due accessi principali sono `In studio · Corsi` e `Online · 0–12 mesi · Consulenza sonno`.
- Il pannello corsi introduce l'offerta con `Imparare insieme, provare davvero.` e rimanda alla panoramica con `Scopri tutti i corsi`.
- Il menu mobile si apre con `Da dove vuoi partire?` e `Scegli il percorso più vicino a ciò che serve oggi.`.
- `Prestazioni infermieristiche`, `Chi sono` e `Domande frequenti` restano collegamenti secondari, sempre accessibili.

## Testimonianze

- Fonte disponibile: feedback spontanei del corso di accompagnamento alla nascita.
- Pubblicazione: solo dopo autorizzazione, eventualmente in forma anonima.
- Regola editoriale: si possono correggere refusi minimi, ma non alterare significato, tono o risultato dichiarato.
- Non attribuire una testimonianza sulla nascita alla consulenza del sonno o ad altri servizi.
- Conservare la prova del consenso fuori dal repository pubblico e secondo la policy privacy.

## Inventario immagini in uso

| File | Dimensioni | Uso corrente | Stato |
|---|---:|---|---|
| `static/img/selene-hero-home.jpg` | 1920×1280 | Hero homepage, Open Graph e dati strutturati; PDF pilota | Approvata come immagine principale provvisoria |
| `static/img/selene-chi-sono.jpg` | 1066×1600 | Pagina Chi sono; PDF pilota | In uso |
| `static/img/selene-consulenze.jpg` | 1280×1920 | Homepage e landing sonno | In uso |
| `static/img/selene-corsi.jpg` | 1280×1920 | Homepage, corsi e prima della nascita | In uso |
| `static/img/selene-dopo-nascita.jpg` | 1280×1920 | Dopo la nascita e disostruzione nell'elenco corsi | In uso; verificare se è la scelta più specifica per disostruzione |
| `static/img/selene-blsd.jpg` | 1280×1920 | Elenco corsi BLSD | In uso |
| `static/img/selene-prestazioni.jpg` | 1920×1280 | Prestazioni infermieristiche | In uso |
| `static/img/placeholder.png` | 600×600 | Laboratori per l'infanzia | Da sostituire prima del lancio |
| `static/img/logo.PNG` | 1024×1024 | Logo chiaro, favicon e materiali | In uso; normalizzare il nome con i riferimenti `logo.png` prima del deploy Linux |
| `static/img/logo_black.png` | 469×589 | Login e materiali PDF | In uso |

## Immagini presenti ma non assegnate

| File | Dimensioni | Stato |
|---|---:|---|
| `static/img/foto1.jpg` | 2675×2499 | Non usata nei template; classificare o archiviare |
| `static/img/foto2.jpg` | 4928×3264 | Non usata nei template; classificare o archiviare |
| `static/img/foto3.jpg` | 4295×6442 | Non usata nei template; classificare o archiviare |
| `static/img/foto4.jpg` | 6720×4480 | Non usata nei template; classificare o archiviare |
| `static/img/foto5.jpg` | 3600×5400 | Non usata nei template; classificare o archiviare |

Prima di assegnarle verificare soggetto, consenso, qualità, ritaglio mobile e relazione con la pagina. Rinominare poi le immagini con nomi descrittivi; evitare di mantenere nomi generici come `foto1.jpg` nel catalogo definitivo.

## Materiali PDF

| File | Destinatari | Stato |
|---|---|---|
| `output/pdf/percorso_sonno_pilota.pdf` | Clienti selezionati per il primo test | Materiale pilota |
| `output/pdf/consulenza_sonno_opzioni_e_prezzi.pdf` | Famiglie già interessate che chiedono percorso e prezzi | Materiale diretto |
| `output/pdf/consulenza_sonno_opzioni_prezzi_senza_foto.pdf` | Stesso pubblico, senza fotografia iniziale | Versione preferita per clienti che già conoscono Selene |

I generatori sono in `tools/genera_pdf_percorso_sonno.py` e `tools/genera_pdf_opzioni_sonno.py`. Se cambiano palette, naming o offerta, aggiornare sia i generatori sia i PDF prodotti.

## Materiali mancanti o da confermare

- Fotografia definitiva per i laboratori dell'infanzia.
- Selezione e rinomina delle cinque fotografie generiche.
- Eventuali nuove fotografie professionali promesse prima del push grafico finale.
- Testimonianze autorizzate e selezionate per il sito.
- Fotografia o composizione Open Graph definitiva.
- Informazioni complete e fonti per eventuali contenuti sanitari approfonditi.
- Contenuti coordinati per il lancio social.

## Criteri di selezione

Ogni immagine deve avere:

- funzione chiara nella pagina;
- consenso adeguato;
- soggetto leggibile anche su mobile;
- ritaglio compatibile con il componente;
- testo alternativo descrittivo e non promozionale;
- dimensioni ottimizzate senza perdere qualità.

Non aggiungere immagini soltanto per riempire uno spazio.
