document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('[data-call-sonno-form]');
    if (!form) return;

    const dataInput = document.getElementById('data-call-sonno');
    const oraSelect = document.getElementById('ora-call-sonno');
    const stato = form.querySelector('[data-slot-status]');
    const altroWrapper = form.querySelector('[data-other-difficulty]');
    const altroInput = document.getElementById('difficolta_altro');
    const difficoltaInputs = form.querySelectorAll('input[name="difficolta_principale"]');

    function aggiornaAltro() {
        const selezionata = form.querySelector('input[name="difficolta_principale"]:checked');
        const mostra = selezionata && selezionata.value === 'Altro';
        altroWrapper.hidden = !mostra;
        altroInput.required = Boolean(mostra);
        if (!mostra) altroInput.value = '';
    }

    async function aggiornaOrari() {
        const data = dataInput.value;
        if (!data) {
            oraSelect.disabled = true;
            stato.textContent = 'Seleziona prima un giorno.';
            return;
        }

        const valorePrecedente = oraSelect.value;
        oraSelect.disabled = true;
        stato.textContent = 'Controllo gli impegni in calendario…';
        try {
            const risposta = await fetch('/api/orari-call-sonno/' + encodeURIComponent(data), {
                headers: {'Accept': 'application/json'},
            });
            if (!risposta.ok) throw new Error('availability');
            const dati = await risposta.json();
            const occupati = new Set(dati.occupati || []);
            let liberi = 0;
            Array.from(oraSelect.options).forEach(function (opzione) {
                if (!opzione.value) return;
                opzione.disabled = occupati.has(opzione.value);
                if (!opzione.disabled) liberi += 1;
            });
            oraSelect.disabled = false;
            if (valorePrecedente && !occupati.has(valorePrecedente)) {
                oraSelect.value = valorePrecedente;
            } else if (occupati.has(valorePrecedente)) {
                oraSelect.value = '';
            }
            stato.textContent = liberi ? liberi + ' orari disponibili.' : 'Nessun orario disponibile: scegli un altro giorno.';
        } catch (errore) {
            oraSelect.disabled = true;
            stato.textContent = 'Non riesco a verificare gli orari. Riprova tra poco o scrivi a Selene su WhatsApp.';
        }
    }

    difficoltaInputs.forEach(function (input) {
        input.addEventListener('change', aggiornaAltro);
    });
    dataInput.addEventListener('change', aggiornaOrari);
    aggiornaAltro();
    aggiornaOrari();
});
