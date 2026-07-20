# Mappa del sito e flussi

Ultimo aggiornamento: 16 luglio 2026.

## Principio di architettura

Il sito è una vetrina autorevole con un retrobottega gestionale leggero. I percorsi non devono convergere tutti su WhatsApp o su un'unica prenotazione generica.

Le priorità commerciali sono:

1. corsi in presenza;
2. consulenza del sonno;
3. prestazioni infermieristiche, sempre accessibili ma secondarie nella gerarchia promozionale.

## Pagine pubbliche principali

| Route | Scopo | Azione principale |
|---|---|---|
| `/` | Presentare Selene, prova di fiducia e due pilastri | Scoprire i corsi o scegliere l'orario della call sonno |
| `/chi-sono` | Credenziali, metodo e volto umano | Approfondire il servizio pertinente |
| `/iscrizione-corsi` | Elenco delle tipologie di corso | Scegliere un corso |
| `/iscrizione-corsi/<corso_tipo>` | Data disponibile o raccolta interesse | Inviare la richiesta di iscrizione |
| `/corso-accompagnamento-nascita` | Presentare il percorso con cinque professionisti | Iscriversi all'open day disponibile |
| `/iscrizione-accompagnamento/<slug>` | Modulo privato del percorso completo | Confermare l'iscrizione al percorso |
| `/dopo-la-nascita` | Orientare verso attività e supporto dopo la nascita | Scegliere corso, laboratorio o consulenza pertinente |
| `/consulenze-online` | Landing nazionale sul sonno infantile 0-12 mesi | Scegliere l'orario della call gratuita |
| `/prenota-call-sonno` | Prenotazione breve della call gratuita | Riservare provvisoriamente uno slot |
| `/questionario-sonno/<token>` | Questionario privato inviato dopo la call | Preparare la formula concordata |
| `/prestazioni-infermieristiche` | Spiegare le prestazioni in studio | Accedere alla prenotazione sanitaria |
| `/prenota` | Prenotare una prestazione sanitaria | Inviare una richiesta di appuntamento |
| `/faq` | Rimuovere dubbi senza moltiplicare CTA | Proseguire nel flusso appropriato |
| `/privacy` | Informativa sul trattamento dei dati | Nessuna CTA commerciale |

Le pagine di conferma devono spiegare cosa è stato registrato e cosa succede dopo, senza far credere che una richiesta sia già confermata quando richiede verifica manuale.

## Gerarchia della homepage

Ordine da mantenere salvo decisione esplicita:

1. Hero con Selene, una promessa e massimo due CTA: `Scopri i corsi` e `Scegli l’orario della call`.
2. Prova di fiducia: ruolo sanitario, OPI, attività reali.
3. Due pilastri: corsi in presenza e consulenza del sonno.
4. Prossime date disponibili.
5. Corso di accompagnamento alla nascita con cinque professionisti.
6. Metodo di Selene.
7. Testimonianze reali autorizzate.
8. Feed Instagram come prova secondaria delle attività reali, con collegamento diretto al profilo.
9. Prestazioni infermieristiche in fascia secondaria.
10. CTA finale coerente con i due pilastri.

La homepage non deve diventare un catalogo né ripetere gli stessi percorsi nel hero e nella sezione immediatamente successiva.

## Flusso corsi individuali

```text
Homepage/pagina corsi
  → scelta tipologia
  → data disponibile
  → modulo di iscrizione
  → richiesta salvata
  → conferma o ricontatto manuale
```

- L'iscrizione è una richiesta finché non viene introdotto il pagamento anticipato.
- Le iscrizioni di coppia valgono due posti, salvo il percorso nascita completo dove la coppia vale un posto.
- Se il corso è pieno, proporre una data successiva; se non esiste, raccogliere preferenze indicative e creare un ricontatto.
- Le tipologie corso usano stati `Aperto`, `Completo`, `Chiuso`, `Annullato`, `Concluso`.

## Flusso corso di accompagnamento alla nascita

Il percorso ha due livelli distinti.

### Open day pubblico

```text
Pagina prima della nascita
  → data open day
  → modulo pubblico
  → richiesta salvata
  → incontro conoscitivo
```

L'open day serve sia alla famiglia per conoscere i professionisti sia al gruppo di lavoro per conoscere la famiglia.

### Percorso completo privato

```text
Link privato generico
  → edizione del percorso
  → calendario di 9 incontri
  → modulo essenziale
  → iscrizione salvata come Confermato
```

- Il link non compare nella navigazione e non deve essere indicizzato.
- Se viene inoltrato, l'iscrizione resta accettabile.
- Raccogliere solo i dati necessari, inclusa la data presunta del parto; non acquisire altri dati sanitari senza necessità esplicita.
- In admin l'edizione gestisce coppie, incontri, professionisti, presenze ed export PDF.

## Flusso consulenza del sonno

```text
Homepage/campagna/condivisione
  → landing sonno 0-12 mesi
  → prenotazione breve della call gratuita
  → slot riservato subito come In attesa su database e Calendar
  → conferma oppure accordo telefonico e modifica entro il giorno lavorativo successivo
  → call conoscitiva di circa 20 minuti
  → scelta condivisa della formula
  → questionario privato sul sito
  → consulenza mirata oppure percorso personalizzato
```

- La landing deve essere verticale sul sonno e pronta per traffico freddo nazionale.
- Deve chiarire problemi osservabili, differenze indicative tra 0-4 e 5-12 mesi, metodo, formule, confini clinici, FAQ e passo successivo.
- `Consulenza mirata`: una difficoltà circoscritta.
- `Percorso sonno personalizzato`: offerta principale quando più aspetti si influenzano.
- Il pagamento, quando verrà introdotto, avviene dopo la call gratuita.
- La prima data pubblica selezionabile è il giorno lavorativo successivo; le call sono disponibili dal lunedì al venerdì negli spazi liberi.
- Lo slot tecnico dura 30 minuti: circa 20 minuti di call e 10 minuti di margine operativo. Tutti i controlli di disponibilità e gli eventi Calendar usano l'intero blocco.
- Ogni conflitto con prestazioni, corsi, call, eventi manuali o Arzamed/Google Calendar rende lo slot non prenotabile.
- Lo stato `In attesa` blocca immediatamente lo slot ma non equivale a conferma. La pagina e l'email devono dirlo senza ambiguità.
- Se l'orario cambia, Selene concorda prima telefonicamente il nuovo slot; il salvataggio admin vale come accettazione e invia direttamente la conferma. Non esiste uno stato “proposta da accettare”.
- Prima della call vengono richiesti soltanto contatti, età 0-12 mesi, difficoltà principale e slot.
- Il questionario completo viene inviato solo dopo la call, quando la famiglia sceglie una formula. È ospitato sul sito, non indicizzato e protetto da token personale non prevedibile.
- WhatsApp resta il canale secondario per chi è indeciso, non sostituisce la prenotazione dedicata.
- La consulenza non formula diagnosi, non prescrive terapie e non sostituisce il pediatra.

### Percorso dalla campagna

```text
Annuncio o contenuto social
  → `/consulenze-online`
  → `Scegli l’orario della call`
  → `/prenota-call-sonno`
  → slot provvisorio e successiva conferma
```

- La campagna iniziale dura tre mesi e promuove il servizio 0-12 mesi senza creare una diversa offerta per ogni creatività.
- Ogni annuncio può partire da una difficoltà osservabile, come addormentamento, risvegli o pisolini, ma deve rimandare alla stessa landing e allo stesso flusso.
- Un eventuale targeting limitato ad Abruzzo e regioni confinanti serve solo a controllare la spesa: la pagina, l'idoneità e l'erogazione online restano nazionali.
- WhatsApp può aiutare chi non è pronto a prenotare, ma non compete visivamente con la CTA principale.

## Flusso prestazioni sanitarie

```text
Pagina prestazioni
  → `/prenota`
  → scelta servizio/data/orario
  → richiesta salvata come In attesa
  → conferma manuale
  → sincronizzazione Calendar ed email
```

- Le prestazioni sanitarie non condividono il form con corsi o consulenze.
- Gli appuntamenti a domicilio non sono prenotabili direttamente: richiedono contatto e valutazione di zona e fattibilità.
- La modifica di un appuntamento deve riportarlo a `In attesa` e notificare lo studio.
- Regola desiderata per modifica/annullamento: fino a 24 ore prima da martedì a sabato; per il lunedì entro il sabato precedente alle 12:00.

## Flusso aziende e gruppi

```text
Pagina corso/richiesta diretta
  → contatto con contesto aziendale
  → valutazione sede, partecipanti e data
  → proposta manuale
```

Le aziende non devono utilizzare il form individuale. CTA consigliata: `Richiedi il corso in studio o in azienda`.

## Uso di WhatsApp

WhatsApp è appropriato per:

- genitori indecisi sulla call sonno;
- aziende e gruppi;
- persone che non trovano una data adatta.

Non deve diventare un widget indistinto o sostituire un modulo specifico già disponibile.

## SEO e autorevolezza

- Un solo `h1` descrittivo per pagina.
- Titolo, meta description, canonical e Open Graph specifici.
- Dati strutturati `MedicalBusiness` per la sede e `Service` per il sonno.
- Ruolo di Selene, iscrizione OPI Pescara, sede e contatti visibili.
- Fonti affidabili quando vengono fatte affermazioni cliniche o di sicurezza.
- Il titolo breve della homepage nella scheda browser è `S.C. Studio Infermieristico`.

## Misurazione delle conversioni

Le CTA principali devono avere `data-conversion`. Distinguere almeno:

- corsi;
- call sonno;
- prestazioni;
- aziende/gruppi.

`static/js/conversion-tracking.js` invia eventi solo dopo il consenso e quando GA4 è disponibile. Prima di una campagna verificare la coerenza tra annuncio, landing, evento, messaggio/modulo e gestione del contatto.

## Evoluzioni previste

- Quiz guidato `Da dove parto?` per chi non sa quale servizio scegliere.
- Prenotazione e pagamento dedicati alle consulenze.
- Landing verticali per campagne specifiche: sonno/primi mesi, disostruzione, open day nascita.
- Pagamento online soltanto quando policy, stati, email, capienza e calendario sono stabili.
