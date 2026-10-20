# Riconciliazione della roadmap post-patch — 20 ottobre 2026

Questa revisione sostituisce, per l'operatività corrente, la roadmap allegata `ROADMAP_POST_PATCH_2026-10-20 (7).md`. Priorità, stati e sequenza hanno una sola fonte: [ROADMAP.md](ROADMAP.md). Le verifiche sono in [PRE_GO_LIVE_CHECKLIST.md](PRE_GO_LIVE_CHECKLIST.md); la decisione del committente è D-123.

## Cambiamento approvato

Pubblicare `scstudioinfermieristico.it` nel minor tempo possibile, completando i controlli essenziali dei flussi esistenti. PayPal è sospeso fino a nuovo ordine. Il percorso sonno usa il bonifico con conferma manuale. Campagna, GA4/Meta, nuove funzioni gestionali e redesign seguono la stabilizzazione del dominio e non sono prerequisiti del GO.

## Patch applicata localmente

Base `main`: `dd6c2be`. PR #16: due commit, ultimo `eefab033`, nove file; CI storica della PR: 468 Python superati, 7 PostgreSQL opt-in saltati e 54 JavaScript superati. La versione locale include inoltre:

- validatore CSRF che rifiuta anche input non ASCII senza generare eccezioni;
- preflight prima delle migrazioni nella checklist;
- PayPal non esposto né accettato per nuove scelte, anche con link legacy configurati;
- gestione 400 delle date impossibili nell'API call;
- esclusione in modifica del solo appuntamento/evento, senza rimuovere altre occupazioni;
- contrasto corretto del logo admin e aggiornamento della cache CSS.

I risultati CI originari non certificano questi adattamenti; gli esiti della candidata sono registrati nella checklist. Applicazione locale non equivale a merge, deploy o GO.

## Correzioni rispetto alla roadmap allegata

- Non affermare che la patch sia distribuita o assente da Render senza riconciliare il servizio.
- Il primo cutover legacy richiede conteggi zero **prima** di `db upgrade`; se ci sono dati, fermarsi e decidere la preservazione.
- Su schema A4/post-A4 già applicato, `--allow-applied` può accettare dati presenti e non restituisce un inventario dei conteggi. Non richiede un nuovo backfill; usare conteggi aggregati separati quando necessari.
- Con DB vuoto registrare l'evidenza senza creare dump inutili. Con dati da preservare, protezione e rollback precedono gli interventi rischiosi.
- Non perdere i rilievi dell'audit precedente: la prova concorrente PostgreSQL è stata eseguita e ha riprodotto le doppie richieste; il committente ha accettato il rischio e rinviato la correzione dopo la pubblicazione (D-125). Non è più un blocco al lancio. Stato e altre prove sono nel [resoconto](TEST_AUTONOMI_2026-10-20.md) e nella roadmap canonica.

## Prossimo passaggio esterno

Riconciliare commit live, Alembic e configurazione non segreta di Render; preparare la release candidata verificata per il deploy privato, poi chiudere gli smoke test e il GO sul dominio secondo la roadmap. Nessun collaudo storico attesta da solo lo stato attuale del servizio.
