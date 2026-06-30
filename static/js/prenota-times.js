document.addEventListener('DOMContentLoaded', function() {
    const dateInput = document.getElementById('data');
    const timeSelect = document.getElementById('ora');

    function aggiornaOrariDisabilitati() {
        const dataSelezionata = dateInput.value;
        if (!dataSelezionata) {
            // Abilita tutte le opzioni se nessuna data selezionata
            Array.from(timeSelect.options).forEach(opzione => {
                if (opzione.value !== '') {
                    opzione.disabled = false;
                }
            });
            return;
        }

        // Recupera gli orari occupati per la data selezionata
        fetch(`/api/orari-occupati/${dataSelezionata}`)
            .then(risposta => risposta.json())
            .then(orariOccupati => {
                // Abilita tutte le opzioni prima
                Array.from(timeSelect.options).forEach(opzione => {
                    if (opzione.value !== '') {
                        opzione.disabled = false;
                    }
                });
                // Disabilita gli orari occupati
                orariOccupati.forEach(ora => {
                    const opzione = Array.from(timeSelect.options).find(opt => opt.value === ora);
                    if (opzione) {
                        opzione.disabled = true;
                    }
                });
            })
            .catch(errore => {
                console.error('Errore nel recupero degli orari occupati:', errore);
            });
    }

    // Ascolta i cambiamenti della data
    dateInput.addEventListener('change', aggiornaOrariDisabilitati);

    // Esegue anche al caricamento della pagina nel caso la data sia pre-compilata (da form_data)
    aggiornaOrariDisabilitati();
});