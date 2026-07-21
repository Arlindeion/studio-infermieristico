# Istruzioni per locandine e materiali commerciali

Ultimo aggiornamento: 13 luglio 2026.

## Scopo di questo documento

Queste istruzioni sono vincolanti per qualsiasi AI che debba progettare, scrivere o aggiornare:

- locandine digitali;
- PDF informativi o commerciali;
- schede di servizio inviate tramite WhatsApp;
- materiali coordinati per campagne e social;
- varianti grafiche derivate dai contenuti del sito.

Il materiale deve sembrare parte dello stesso progetto del sito di S.C. Studio Infermieristico. Non deve introdurre un'identità parallela, modificare il posizionamento o trasformare Selene in un brand impersonale.

## Contesto obbligatorio

Prima di lavorare leggere, nell'ordine:

1. `AGENTS.md`;
2. `docs/PROJECT_BRIEF.md`;
3. `docs/BRAND_SYSTEM.md`;
4. `docs/SITE_MAP_AND_FLOWS.md`;
5. `docs/DECISIONS.md`;
6. `docs/CONTENT_AND_ASSETS.md`;
7. questo documento.

Consultare anche `docs/ROADMAP.md` quando il materiale è legato a un lancio o a una campagna e `docs/OPERATIONS.md` quando occorre generare o pubblicare un PDF.

In caso di contraddizione, `AGENTS.md` prevale. I dati relativi all'attività provengono da `PROJECT_BRIEF.md`; palette e tono da `BRAND_SYSTEM.md`; immagini e testi approvati da `CONTENT_AND_ASSETS.md`.

Non usare la cronologia di una conversazione come unica fonte di verità.

## Missione da preservare

La comunicazione deve far percepire rapidamente:

> Qui c'è una professionista sanitaria che sa cosa fa, parla ai genitori in modo umano e può essere la scelta giusta per la mia famiglia.

S.C. Studio Infermieristico è la sede e il contenitore professionale. Selene Campetta è il riferimento umano per famiglie e neogenitori.

Ogni materiale deve unire:

- autorevolezza sanitaria;
- vicinanza e ascolto;
- concretezza pratica;
- linguaggio comprensibile;
- crescita controllata, senza pressione commerciale eccessiva.

L'obiettivo iniziale è generare contatti qualificati e aumentare il valore percepito, non massimizzare il numero di richieste o vendere con urgenza artificiale.

## Informazioni da ottenere prima di progettare

Prima di iniziare devono essere chiari:

- servizio o evento da promuovere;
- pubblico: freddo, già interessato o cliente che conosce Selene;
- canale: PDF WhatsApp, email, Instagram, landing o altro;
- azione richiesta alla persona;
- data, luogo, formato e disponibilità, se pertinenti;
- presenza o assenza del prezzo;
- fotografie autorizzate disponibili;
- scadenza reale del materiale.

Se manca un'informazione che cambia offerta, gerarchia o CTA, chiederla prima di produrre il materiale. Non inventare date, disponibilità, prezzi, qualifiche, risultati, testimonianze o partnership.

Se il dato mancante è soltanto esecutivo e può essere sostituito senza alterare il progetto, usare un segnaposto chiaramente riconoscibile e segnalarlo.

## Pubblico e livello di familiarità

### Pubblico freddo

Una persona che non conosce Selene deve capire:

- chi è la professionista;
- per chi è il servizio;
- quale difficoltà affronta;
- quale metodo viene utilizzato;
- perché può fidarsi;
- qual è il prossimo passo.

Usare fotografia reale, credenziale professionale e una breve prova di valore. Non presumere conoscenza dello studio.

### Famiglie già interessate

Ridurre la parte introduttiva e rispondere direttamente a:

- differenza tra le opzioni;
- cosa comprende ogni formula;
- quando scegliere l'una o l'altra;
- prezzo, se richiesto;
- come procedere.

L'offerta breve non deve far apparire inutile il percorso principale.

### Clienti che già conoscono Selene

Non sprecare la prima schermata con una presentazione generica o una fotografia puramente identitaria. Per il PDF con le due opzioni sonno è stata approvata la versione senza la fotografia iniziale con il cuore in mano.

La riconoscibilità deve restare attraverso logo, palette, tipografia, tono e firma rossa.

## Gerarchia commerciale

Mantenere la stessa priorità del sito:

1. corsi in presenza;
2. consulenza del sonno;
3. prestazioni infermieristiche come flusso separato.

Una locandina può essere verticale su un solo servizio, ma non deve cambiare il posizionamento complessivo dello studio. Non presentare le prestazioni come offerta civetta e non trasformare la consulenza del sonno nel nome generale di tutta l'attività.

## Sistema visivo obbligatorio

### Palette

| Ruolo | Colore | Utilizzo |
|---|---|---|
| Salvia identitario | `#B1BBA5` | Copertine, fasce, grandi superfici e riconoscibilità |
| Salvia chiarissimo | `#E5E9E0` | Fondi informativi e separazioni leggere |
| Carta | `#F7F5F1` | Fondo principale e aree di lettura |
| Verde azione | `#506A59` | CTA e piccoli pannelli con testo bianco |
| Verde testo | `#304438` | Titoli e testo sul salvia |
| Verde profondo | `#3F5948` | Footer, chiusure e piccoli contrasti |
| Rosso cuore | `#9A4E56` | Firma, linea, bordo o micro-etichetta |

Sul salvia `#B1BBA5` non usare testo bianco: usare `#304438`. Il bianco può essere usato su `#506A59` e `#3F5948`.

Il rosso è una firma, non un colore dominante. Non introdurre rosa maternità, verdi smeraldo, turchesi sanitari o palette pastello generiche.

### Tipografia

- `Bricolage Grotesque`: titoli brevi, apertura e messaggi principali.
- `Atkinson Hyperlegible`: testo, prezzi, elenchi, FAQ, note e contatti.

Se il software non permette questi font, usare un'alternativa soltanto dopo aver verificato leggibilità e somiglianza funzionale. Non aggiungere font decorativi, calligrafici o infantili.

### Logo

- Usare il logo ufficiale disponibile in `static/img/`.
- Non deformarlo, ricolorarlo liberamente o inserirlo su un fondo che ne riduce il contrasto.
- Lasciare spazio libero intorno.
- Non usare il logo come decorazione ripetuta.
- Verificare il nome effettivo del file: il repository registra ancora `logo.PNG`, mentre alcuni riferimenti applicativi usano `logo.png`.

### Firma rossa

La linea rossa continua può:

- collegare le fasi di un percorso;
- separare due opzioni;
- sottolineare un concetto decisivo;
- guidare verso la CTA.

Non aggiungerla automaticamente a ogni titolo o card.

## Fotografie e immagini

Usare in priorità:

1. fotografie reali di Selene;
2. fotografie reali dello studio, corsi, materiali e attività;
3. `static/img/placeholder.png` solo quando dichiaratamente provvisorio.

Non usare:

- fotografie stock di madri e bambini;
- persone generate artificialmente presentate come clienti reali;
- illustrazioni casuali o stili cartoon non appartenenti al brand;
- immagini cliniche allarmistiche;
- fotografie di minori o partecipanti senza consenso appropriato.

Non coprire volti, mani o gesti con gradienti pesanti. Il ritaglio deve funzionare anche sullo schermo di uno smartphone.

Consultare `CONTENT_AND_ASSETS.md` per sapere quali immagini sono assegnate, provvisorie o ancora da classificare.

## Struttura consigliata di una locandina digitale

Ogni materiale deve rispondere, nell'ordine più breve possibile, a queste domande:

1. Che cos'è?
2. Per chi è?
3. Quale problema concreto o passaggio affronta?
4. Cosa ottiene, impara o comprende la persona?
5. Come si svolge: durata, formato, luogo o modalità online?
6. Chi conduce e con quale ruolo professionale?
7. Cosa succede dopo il contatto?
8. Qual è l'unica azione principale da compiere?

Struttura di riferimento:

```text
Logo/nome essenziale
Titolo specifico
Sottotitolo centrato sul bisogno
Per chi è
Cosa comprende o cosa si impara
Formato, data e luogo
Prova di fiducia o confine professionale
CTA principale
Contatti e note strettamente necessarie
```

Non è obbligatorio usare tutti i blocchi se il pubblico conosce già Selene. È invece obbligatorio che l'azione successiva sia evidente.

## Regole di scrittura

- Scrivere in italiano semplice, concreto e corretto.
- Rivolgersi alla persona con tono umano, generalmente usando il `tu`.
- Preferire frasi brevi e verbi attivi.
- Descrivere segnali, gesti, routine, materiali o passaggi osservabili.
- Spiegare eventuali termini tecnici.
- Limitare il testo a ciò che aiuta la decisione.
- Usare titoli informativi, non slogan generici.

Evitare:

- `SOS neomamma` come nome del servizio;
- promesse come `risolve il sonno`, `notti serene garantite` o equivalenti;
- `servizio su misura` senza spiegare in cosa consiste;
- pressione come `ultimissima occasione` se non è un fatto reale;
- colpevolizzazione, allarmismo e confronto denigratorio con altri professionisti;
- emoji decorative o elenchi costruiti solo per riempire spazio.

## CTA e contatti

Ogni materiale deve avere una sola CTA primaria. Esempi approvati:

- `Scegli l’orario della call`
- `Iscrizione individuale`
- `Scopri le prossime date`
- `Prenota`
- `Richiedi il corso in studio o in azienda`

WhatsApp è adatto a:

- famiglie indecise sulla call sonno;
- aziende e gruppi;
- persone che non trovano una data.

Quando esiste un modulo specifico, usare il modulo come CTA. Recuperare sempre URL, telefono e contatti dalle fonti correnti del sito; non riscriverli a memoria.

Nei PDF rendere link, indirizzo email e numero di telefono cliccabili quando tecnicamente possibile.

### Campagna iniziale sulla consulenza del sonno

Il test dura tre mesi e promuove la consulenza del sonno 0-12 mesi. Per ogni annuncio, video o contenuto sponsorizzato:

- partire da una sola difficoltà osservabile, non dal tema generico del sonno;
- mantenere `Scegli l’orario della call` come CTA primaria verso la landing e il calendario;
- usare l'identità dello studio e la presenza reale di Selene, senza creare un sottobrand;
- non inventare testimonianze, casi o risultati: le prove specifiche del servizio saranno aggiunte solo quando reali e autorizzate;
- non restringere la promessa alla sola area geografica dell'annuncio: il servizio resta nazionale e online;
- trattare un eventuale targeting su Abruzzo e regioni confinanti come scelta di distribuzione legata al budget.

Il primo test è nazionale su Meta/Instagram: massimo 200 €, verifica dopo 100 €, due angoli iniziali (`risvegli frequenti` e `addormentamento con forte supporto`) e arresto/rallentamento a 10 call prenotate nella settimana. Consultare `PROJECT_BRIEF.md` e `DECISIONS.md` prima di produrre la serie definitiva.

## Prezzi

Il prezzo non è la leva principale della comunicazione pubblica.

- Inserirlo quando il materiale è destinato a persone che lo hanno chiesto o quando il compito lo richiede esplicitamente.
- Presentare prima differenze, appropriatezza e contenuto dell'offerta.
- Non trasformare la formula più economica in un confronto che svaluta quella principale.
- Non pubblicare costi, margini, accordi con collaboratori o obiettivi economici presenti nel brief.
- Verificare ogni prezzo in `PROJECT_BRIEF.md` e nella richiesta corrente prima di generare il file.

## Istruzioni specifiche per la consulenza del sonno

Naming:

- `Consulenza del sonno` o `Consulenza sonno`;
- fascia attuale: 0-12 mesi;
- non mescolare ciuccio, spannolinamento e consulenze generiche nella stessa offerta.

Le tre formule hanno funzioni differenti:

- `Consulenza mirata` — 75 €, dedicata a una singola difficoltà circoscritta;
- `Percorso sonno personalizzato` — 180 €, proposta principale quando più aspetti si influenzano tra loro.
- `Percorso sonno con affiancamento` — 320 €, stesso percorso con 60 giorni di WhatsApp entro i confini pubblicati.

La formula breve deve apparire appropriata a casi limitati, non come versione scontata del percorso.

La call conoscitiva gratuita di circa 20 minuti precede l'eventuale pagamento e serve a capire se il servizio è adatto.

I prezzi sono visibili prima della prenotazione. Non usare `premium` come nome pubblico: l'affiancamento descrive il valore senza introdurre un registro estraneo al brand.

Inserire in modo leggibile, senza tono difensivo:

- la consulenza non formula diagnosi;
- non prescrive terapie;
- non sostituisce il pediatra;
- non promette risultati garantiti;
- eventuali segnali clinici richiedono il professionista sanitario appropriato.

Per il materiale pilota rivolto a clienti selezionati è possibile spiegare che il servizio è in fase di test. Per il materiale destinato a famiglie già clienti evitare una lunga introduzione personale e la fotografia iniziale con il cuore in mano.

## Istruzioni specifiche per corsi e laboratori

### BLSD

- Comunicarlo come investimento concreto nella sicurezza degli ambienti.
- Chiarire destinatari, parte pratica, certificazione quando pertinente, data, durata e luogo.
- Non usare un tono emergenziale o immagini traumatiche.

### Disostruzione pediatrica e tagli sicuri

- Usare sempre il nome completo.
- Evidenziare gesti pratici, prevenzione a tavola e destinatari: genitori, nonni e caregiver.
- Distinguere iscrizione singola e di coppia solo se il prezzo viene richiesto.

### Corso di accompagnamento alla nascita

- Usare il nome ufficiale.
- Valorizzare la presenza di cinque professionisti: infermiera, ostetrica, psicologa, osteopata e nutrizionista.
- Il punto distintivo è la visione a 360 gradi dalla gravidanza al rientro a casa.
- Distinguere chiaramente open day gratuito e percorso completo di nove incontri.
- Il percorso è pensato e prezzato per la coppia.

### Laboratori per l'infanzia

- Specificare se si tratta di alimentazione/svezzamento oppure gioco e sviluppo.
- Scrivere cosa farà il bambino e cosa porterà a casa il genitore in termini di comprensione o strumenti.
- Non presentare il laboratorio come terapia se non lo è.

## Prestazioni infermieristiche

Le locandine sulle prestazioni devono mantenere un tono sanitario chiaro e distinto dai materiali per corsi e consulenze.

- Indicare se la prestazione è in studio o richiede valutazione domiciliare.
- Gli appuntamenti a domicilio non devono sembrare prenotabili automaticamente.
- Usare `Prenota` soltanto quando il flusso porta realmente a `/prenota`.
- Non usare prezzi bassi come esca né suggerire equivalenza con servizi non sanitari.

## Formati digitali

### PDF inviato via WhatsApp o email

- Preferire una o due pagine, salvo contenuti che richiedano realmente più spazio.
- Progettare per la lettura su smartphone, non soltanto per la stampa A4.
- Titoli e prezzi devono restare leggibili senza zoom eccessivo.
- Mantenere margini sicuri, testo selezionabile e link cliccabili.
- Incorporare i font quando possibile.
- Ottimizzare le immagini e mantenere il file abbastanza leggero per l'invio.
- Non inserire informazioni essenziali esclusivamente dentro una fotografia.

### Contenuto social

- Non limitarsi a ritagliare il PDF A4.
- Preparare una composizione dedicata al formato richiesto, per esempio 1080×1350 per un post verticale.
- Una singola schermata comunica un solo messaggio principale.
- Per caroselli, distribuire il ragionamento in passaggi con continuità visiva e CTA finale.
- Verificare che testi e dettagli non siano coperti dall'interfaccia della piattaforma.

## File, sorgenti e versioni

- Salvare i PDF finali in `output/pdf/`.
- Conservare la sorgente riproducibile in `tools/` quando il PDF viene generato via codice.
- Usare nomi descrittivi, per esempio `consulenza_sonno_clienti_opzioni_prezzi.pdf`.
- Non sovrascrivere un materiale approvato con una variante sperimentale senza rendere chiara la differenza.
- Quando cambia un dato condiviso, aggiornare sorgente, PDF prodotto e `CONTENT_AND_ASSETS.md`.
- Non inserire nelle sorgenti password, dati clienti, URL privati o testimonianze non autorizzate.

## Procedura di lavoro per l'AI

1. Leggere le fonti obbligatorie.
2. Controllare lo stato Git e preservare modifiche esistenti.
3. Identificare pubblico, canale, obiettivo e CTA.
4. Verificare dati, prezzi, date, immagini e autorizzazioni.
5. Definire la gerarchia prima di decorare.
6. Scrivere il testo usando naming e tono approvati.
7. Applicare palette, font, fotografia e firma rossa.
8. Generare il file mantenendo una sorgente riproducibile.
9. Renderizzare tutte le pagine del PDF come immagini.
10. Controllare visivamente ogni pagina, anche simulando la lettura su smartphone.
11. Correggere overflow, spazi vuoti casuali, gerarchia, contrasto e link.
12. Aggiornare `CONTENT_AND_ASSETS.md` se nasce un materiale definitivo.
13. Riportare file creati, verifiche eseguite e dati ancora provvisori.

## Checklist finale

### Missione e contenuto

- È evidente che dietro il servizio c'è Selene, professionista sanitaria?
- Il materiale affronta un bisogno concreto senza promettere risultati?
- Il pubblico capisce per chi è, cosa comprende e cosa succede dopo?
- È presente una sola CTA primaria?
- Naming, prezzi, date e qualifiche sono verificati?

### Coerenza grafica

- Palette e contrasto rispettano il brand system?
- Sono usati Bricolage Grotesque e Atkinson Hyperlegible?
- Il rosso resta una firma e non domina?
- Le fotografie sono reali, appropriate e autorizzate?
- Il risultato evita l'estetica generica da template AI?

### Qualità del file

- Ogni pagina è stata renderizzata e controllata?
- Il testo è leggibile su smartphone?
- Non ci sono elementi tagliati, sovrapposti o troppo vicini ai margini?
- Link e contatti funzionano?
- Il peso del PDF è adatto all'invio?
- La sorgente permette di rigenerarlo?

### Sicurezza

- Non sono presenti dati personali non necessari?
- Immagini e testimonianze sono autorizzate?
- Nessuna credenziale o informazione privata è inclusa nel file o nei metadati?

Una locandina non è conclusa soltanto perché il PDF è stato generato: deve essere visivamente verificata e coerente con la missione del sito.
