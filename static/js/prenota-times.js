document.addEventListener('DOMContentLoaded', function() {
    const dateInput = document.getElementById('data');
    const timeSelect = document.getElementById('ora');
    const festiviFissi = new Set([
        '01-01', '01-06', '04-25', '05-01', '06-02',
        '08-15', '11-01', '12-08', '12-25', '12-26',
    ]);

    function dataLocaleDaInput(dataStr) {
        const [anno, mese, giorno] = dataStr.split('-').map(Number);
        return new Date(anno, mese - 1, giorno);
    }

    function formattaMeseGiorno(data) {
        return `${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}`;
    }

    function calcolaPasqua(anno) {
        const a = anno % 19;
        const b = Math.floor(anno / 100);
        const c = anno % 100;
        const d = Math.floor(b / 4);
        const e = b % 4;
        const f = Math.floor((b + 8) / 25);
        const g = Math.floor((b - f + 1) / 3);
        const h = (19 * a + b - d - g + 15) % 30;
        const i = Math.floor(c / 4);
        const k = c % 4;
        const l = (32 + 2 * e + 2 * i - h - k) % 7;
        const m = Math.floor((a + 11 * h + 22 * l) / 451);
        const mese = Math.floor((h + l - 7 * m + 114) / 31);
        const giorno = ((h + l - 7 * m + 114) % 31) + 1;
        return new Date(anno, mese - 1, giorno);
    }

    function isFestivo(data) {
        const pasquetta = calcolaPasqua(data.getFullYear());
        pasquetta.setDate(pasquetta.getDate() + 1);
        return (
            data.getDay() === 0
            || festiviFissi.has(formattaMeseGiorno(data))
            || data.toDateString() === pasquetta.toDateString()
        );
    }

    function orariChiusiPerData(dataSelezionata) {
        const data = dataLocaleDaInput(dataSelezionata);
        if (isFestivo(data)) {
            return Array.from(timeSelect.options)
                .map(opzione => opzione.value)
                .filter(Boolean);
        }

        if (data.getDay() === 6) {
            return Array.from(timeSelect.options)
                .map(opzione => opzione.value)
                .filter(ora => ora && ora > '12:00');
        }

        return [];
    }

    function applicaOrariDisabilitati(orariDaDisabilitare) {
        Array.from(timeSelect.options).forEach(opzione => {
            if (opzione.value !== '') {
                opzione.disabled = orariDaDisabilitare.includes(opzione.value);
            }
        });

        if (timeSelect.value && orariDaDisabilitare.includes(timeSelect.value)) {
            timeSelect.value = '';
        }
    }

    function aggiornaOrariDisabilitati() {
        const dataSelezionata = dateInput.value;
        if (!dataSelezionata) {
            dateInput.setCustomValidity('');
            // Abilita tutte le opzioni se nessuna data selezionata
            Array.from(timeSelect.options).forEach(opzione => {
                if (opzione.value !== '') {
                    opzione.disabled = false;
                }
            });
            return;
        }

        const orariChiusura = orariChiusiPerData(dataSelezionata);
        dateInput.setCustomValidity(
            orariChiusura.length === timeSelect.options.length - 1
                ? 'Lo studio è chiuso nel giorno selezionato.'
                : ''
        );

        // Recupera gli orari occupati per la data selezionata
        fetch(`/api/orari-occupati/${dataSelezionata}`)
            .then(risposta => risposta.json())
            .then(orariOccupati => {
                applicaOrariDisabilitati([...new Set([...orariChiusura, ...orariOccupati])]);
            })
            .catch(errore => {
                console.error('Errore nel recupero degli orari occupati:', errore);
                applicaOrariDisabilitati(orariChiusura);
            });
    }

    // Ascolta i cambiamenti della data
    dateInput.addEventListener('change', aggiornaOrariDisabilitati);

    // Esegue anche al caricamento della pagina nel caso la data sia pre-compilata (da form_data)
    aggiornaOrariDisabilitati();
});
