# Identità visiva e verbale

Ultimo aggiornamento: 15 luglio 2026.

## Idea guida

L'identità deve unire fiducia sanitaria, calore familiare e riconoscibilità personale. Non deve sembrare una generica attività dedicata alla maternità né una struttura sanitaria fredda.

S.C. Studio Infermieristico identifica la sede. Selene è la presenza umana da far emergere nei contenuti rivolti a genitori e famiglie.

## Promessa percepita

Competenza sanitaria, parole semplici e supporto concreto nei passaggi che mettono più in difficoltà i genitori.

La comunicazione descrive metodo, osservazione e strumenti pratici. Non promette serenità assoluta, risultati garantiti, metodi miracolosi o soluzioni valide per ogni bambino.

## Palette ufficiale

I token implementati in `static/css/tokens.css` sono la fonte tecnica dei colori.

| Ruolo | Colore | Uso |
|---|---|---|
| Salvia identitario | `#B1BBA5` | Header, menu mobile, grandi fasce e superfici di brand |
| Salvia chiarissimo | `#E5E9E0` | Fondi informativi e alternanze leggere |
| Carta | `#F7F5F1` | Fondo principale delle pagine |
| Verde azione | `#506A59` | Pulsanti primari e piccoli pannelli funzionali con testo bianco |
| Verde testo | `#304438` | Titoli, navigazione e testo sui fondi salvia |
| Verde profondo | `#3F5948` | Footer e hover; non per grandi superfici commerciali |
| Rosso cuore | `#9A4E56` | Firma, linea continua, bordi e micro-etichette |

Sul salvia `#B1BBA5` utilizzare testo `#304438`, non bianco. Il bianco è riservato a `#506A59` e `#3F5948`, dove il contrasto è sufficiente.

Non introdurre verdi smeraldo, bosco, turchese o “sanitari” freddi come dominanti. Non aggiungere nuovi colori prima di verificare i token già esistenti.

## Tipografia

- `Bricolage Grotesque`: titoli brevi, messaggi commerciali e gerarchia principale.
- `Atkinson Hyperlegible`: testi, moduli, tabelle, FAQ e contenuti informativi.

Non aggiungere altri font senza una ragione funzionale documentata.

## Firma visiva

Una linea rossa sottile richiama sia il cuore anatomico del logo sia il filo del cuore lavorato all'uncinetto. Può:

- collegare passaggi di una sequenza;
- sottolineare una parola importante;
- guidare lo sguardo tra elementi correlati.

Non deve essere ripetuta come decorazione automatica in ogni sezione.

## Fotografia

Le immagini reali sono il principale elemento distintivo:

- Selene in divisa salvia;
- gesti manuali e pratici;
- corsi e attività realmente svolti;
- studio e materiali;
- cuore anatomico e manufatti all'uncinetto;
- dettagli rossi e blu già presenti nell'immaginario personale.

Preferire sempre immagini reali alle fotografie stock. Se manca il materiale definitivo usare `static/img/placeholder.png`, dichiarandolo nell'inventario. Non coprire i volti o i gesti con gradienti pesanti.

Prima di pubblicare immagini con partecipanti, soprattutto minori, verificare il consenso pertinente.

## Logo e naming

- Nome della sede: `S.C. Studio Infermieristico`.
- Riferimento personale: `Selene Campetta`.
- Titolo breve della scheda browser in homepage: `S.C. Studio Infermieristico`.
- Nei contenuti per genitori parlare in prima persona quando è Selene a offrire il supporto.

Il logo deve mantenere spazio sufficiente intorno e contrasto con il fondo. Nell'header salvia usare la variante che resta leggibile con navigazione scura; nel footer profondo usare la variante chiara.

## Header e footer

- Header: fondo salvia identitario, logo e testi verde scuro.
- Footer: verde profondo e testo chiaro.
- Le prestazioni infermieristiche restano nella navigazione, ma non diventano il pulsante dominante.
- La navigazione deve mantenere chiari i due pilastri: corsi e consulenza del sonno.

La scelta del testo scuro nell'header è sia stilistica sia funzionale: crea continuità con la palette dello studio e mantiene contrasto sufficiente sul salvia.

## Componenti e composizione

- Ogni schermata deve avere una priorità visiva riconoscibile.
- Evitare card tutte uguali, sezioni alternate senza funzione e pulsanti a pillola usati ovunque.
- Evitare motivi botanici generici.
- Riutilizzare componenti e spaziature già presenti nei moduli di `static/css/`.
- Mantenere separate le responsabilità: fondamenta in `base.css`, componenti condivisi in `components.css`, homepage e consulenza nei rispettivi moduli e interfaccia gestionale in `admin.css`.
- Il rosso è una firma, non un secondo colore dominante.
- Le CTA devono essere brevi, specifiche e visivamente gerarchizzate.

## Tono di voce

### Deve essere

- competente ma comprensibile;
- calmo, concreto e vicino;
- rispettoso della fatica dei genitori;
- chiaro sui confini clinici;
- orientato a cosa la persona impara, osserva o fa dopo.

### Da evitare

- tono emergenziale come `SOS neomamma`;
- promesse di “notti serene” o risultati certi;
- formule vaghe come “servizi su misura” senza spiegazione;
- colpevolizzazione dei genitori;
- linguaggio infantile o eccessivamente lezioso;
- tecnicismi senza traduzione pratica.

## Naming approvato

- `Consulenza del sonno` o `Consulenza sonno` per il servizio 0-12 mesi.
- `Consulenze genitori` può diventare in futuro un contenitore, ma non è il nome della landing attuale.
- `Corso di accompagnamento alla nascita`.
- `Disostruzione pediatrica e tagli sicuri`.
- `BLSD`, spiegato come investimento nella sicurezza degli ambienti.

## Coerenza tra canali

Sito, social, PDF e locandine devono utilizzare:

- la stessa palette;
- gli stessi due font o equivalenti controllati quando il formato non li supporta;
- fotografie reali riconoscibili;
- una sola CTA primaria per messaggio;
- lo stesso tono e gli stessi nomi dei servizi.

Video generati possono sostenere la frequenza editoriale, ma non devono imitare testimonianze, risultati reali o situazioni cliniche. Devono restare chiaramente coerenti con il sistema visivo e non sostituire la presenza reale di Selene.

## Controlli minimi

Per ogni modifica estetica importante controllare almeno:

- desktop a 1440 px e mobile a 390 px;
- contrasto, focus visibile e target touch;
- assenza di scorrimento orizzontale;
- leggibilità di header, menu mobile, CTA e footer;
- coerenza con palette, font e fotografia;
- comportamento con testi più lunghi e date dinamiche.
