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
