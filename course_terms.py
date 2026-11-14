"""Versioned course terms shared by the public page and confirmation email."""

COURSE_TERMS_VERSION = '2026-11-14'
COURSE_TERMS_UPDATED_LABEL = '14 novembre 2026'
COURSE_TERMS_SECTIONS = (
    ('1. Iscrizione e conferma', (
        'Per il corso di disostruzione pediatrica e tagli sicuri con pagamento online, il modulo è seguito dal versamento su Nexi di un acconto pari al 50% della quota. Il posto è confermato automaticamente solo dopo la verifica del pagamento; viene inviata una email con i dettagli dell’iscrizione.',
        'Un pagamento non completato o soltanto autorizzato non conferma il posto. Le richieste di ricontatto e la lista d’attesa non richiedono pagamenti e non confermano un’iscrizione.',
        'Per gli altri corsi e per le richieste gestite senza pagamento online, l’invio del modulo è una richiesta: il posto viene confermato dallo studio con una successiva comunicazione.',
    )),
    ('2. Quota, acconto e saldo', (
        'Disostruzione pediatrica e tagli sicuri: singolo 34 €, di cui 17 € di acconto online e 17 € di saldo; coppia 60 € complessivi per due persone, di cui 30 € di acconto online e 30 € di saldo. Il saldo del restante 50% si versa in presenza il giorno del corso.',
        'Prima del pagamento sono indicati quota totale, acconto dovuto e saldo residuo. L’acconto è parte del prezzo del corso, non un costo aggiuntivo né una caparra confirmatoria.',
        'Negli altri casi la quota è quella indicata per il corso scelto e si paga in presenza, salvo un diverso accordo espresso con lo studio. L’ambiente Nexi di prova usa operazioni simulate, senza addebiti reali.',
    )),
    ('3. Rinuncia e comunicazioni', (
        'La rinuncia o richiesta di spostamento deve essere comunicata allo studio, tramite email a info@scstudioinfermieristico.it oppure telefono o WhatsApp al 380 631 7175, indicando nominativo e data prenotata.',
        'Si applica lo stesso preavviso della consulenza sonno: per un corso previsto il lunedì, entro le ore 18 del venerdì precedente; per gli altri giorni, almeno 24 ore prima dell’inizio. Se la scadenza cade in un giorno festivo, entro le ore 18 dell’ultimo giorno lavorativo precedente. Tutti gli orari sono riferiti al fuso italiano. In caso di rinuncia comunicata entro questi termini, non si applica la trattenuta per mancata presentazione: l’acconto eventualmente versato viene rimborsato, salvo che il partecipante scelga di trasferirlo a un’altra data concordata con lo studio. Non è dovuto il saldo.',
        'Per le iscrizioni senza anticipo la rinuncia non comporta costi. Restano salvi i diritti inderogabili del consumatore, compreso il diritto di recesso quando applicabile: queste condizioni non li escludono né li limitano.',
    )),
    ('4. Mancata presentazione senza avviso', (
        'Se il partecipante non si presenta e non comunica la rinuncia entro i termini del punto 3 per il corso di disostruzione, perde l’acconto già versato, pari al 50% della quota totale: 17 € per il singolo o 30 € per la coppia. Non viene richiesto il restante 50%.',
        'Se nessuno dei due partecipanti della coppia si presenta senza il preavviso richiesto, si perde l’acconto complessivo di 30 €. Se partecipa una sola persona, viene meno lo sconto coppia di 30 € a persona: si applica la quota singola di 34 €. L’acconto di 30 € già versato viene interamente detratto e il saldo da pagare in presenza è di 4 €. Non si applica un’ulteriore trattenuta per l’altra persona assente.',
        'La trattenuta riguarda soltanto l’acconto relativo a questa iscrizione e non autorizza ulteriori addebiti automatici. Restano salvi i diritti inderogabili previsti dalla legge. Per gli altri corsi con pagamento interamente in presenza non sono previste penali per mancata presentazione.',
    )),
    ('5. Spostamento a un’altra data', (
        'Entro i termini di preavviso del punto 3 il partecipante può chiedere di trasferire l’iscrizione a un’altra edizione. Lo spostamento richiede la disponibilità di posti e la conferma dello studio; se concordato, l’acconto segue la nuova iscrizione senza un secondo pagamento.',
        'Una semplice richiesta di spostamento non prenota automaticamente la nuova data. Se non si concorda un’alternativa e la rinuncia è stata comunicata entro i termini di preavviso, si applica il rimborso previsto al punto 3.',
    )),
    ('6. Modifica o annullamento da parte dello studio', (
        'Lo studio comunica eventuali modifiche di data, orario o sede, riprogrammazioni e annullamenti ai recapiti indicati nell’iscrizione.',
        'Se lo studio annulla il corso, oppure la nuova data o sede proposta non viene accettata, l’acconto è rimborsato integralmente e il saldo non è dovuto. Il trasferimento dell’acconto a una nuova data avviene soltanto con l’accordo del partecipante.',
    )),
    ('7. Condizioni specifiche e contatti', (
        'Le dichiarazioni richieste nel modulo fanno parte delle condizioni del corso: natura informativa e pratica, requisiti per svolgere le esercitazioni in sicurezza ed eventuale rilascio o mancato rilascio di certificazioni.',
        'S.C. Studio Infermieristico — Via C. D’Agnese 43, 65015 Montesilvano (PE). Email: info@scstudioinfermieristico.it. Telefono e WhatsApp: 380 631 7175.',
    )),
)


def course_terms_text():
    sections = [f'Condizioni di iscrizione ai corsi — versione {COURSE_TERMS_VERSION}']
    sections.extend(title + '\n' + '\n'.join(paragraphs) for title, paragraphs in COURSE_TERMS_SECTIONS)
    return '\n\n'.join(sections)
