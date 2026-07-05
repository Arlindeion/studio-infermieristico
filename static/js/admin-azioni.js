// Azioni admin: conferma le azioni per appuntamenti e corsi
document.addEventListener('DOMContentLoaded', function() {
    const adminViewButtons = document.querySelectorAll('[data-admin-target]');
    const adminPanels = document.querySelectorAll('[data-admin-panel]');

    function mostraPannelloAdmin(nomePannello) {
        adminPanels.forEach(panel => {
            panel.classList.toggle('is-hidden', panel.dataset.adminPanel !== nomePannello);
        });
        adminViewButtons.forEach(button => {
            const attivo = button.dataset.adminTarget === nomePannello;
            button.classList.toggle('attivo', attivo);
            button.setAttribute('aria-selected', attivo ? 'true' : 'false');
        });
    }

    if (adminViewButtons.length && adminPanels.length) {
        const pannelloIniziale = window.location.hash === '#admin-corsi' ? 'corsi' : 'prenotazioni';
        mostraPannelloAdmin(pannelloIniziale);

        adminViewButtons.forEach(button => {
            button.addEventListener('click', function() {
                const target = this.dataset.adminTarget;
                mostraPannelloAdmin(target);
                window.history.replaceState(null, '', target === 'corsi' ? '#admin-corsi' : '#admin-prenotazioni');
            });
        });
    }

    // Gestisce i link di azione per gli appuntamenti (conferma, modifica, elimina, ecc.)
    document.querySelectorAll('.btn-azione').forEach(pulsante => {
        // Elabora solo i tag <a> (collegamenti)
        if (tagNameCheck(pulsante, 'a')) {
            pulsante.addEventListener('click', function(e) {
                const messaggio = this.getAttribute('data-confirm');
                if (messaggio && !confirm(messaggio)) {
                    e.preventDefault();
                }
                // Se confermato, il browser seguirà naturalmente il collegamento.
            });
        }
    });

    // Funzione ausiliaria per controllare il nome del tag (case-insensitive)
    function tagNameCheck(elemento, nomeTag) {
        return elemento.tagName.toLowerCase() === nomeTag.toLowerCase();
    }

    const tipoCorso = document.getElementById('tipo-corso-admin');
    const titoloCorso = document.getElementById('titolo-corso-admin');
    const durataCorso = document.getElementById('durata-corso-admin');
    let titoloCompilatoAutomaticamente = '';

    if (tipoCorso && titoloCorso && durataCorso) {
        tipoCorso.addEventListener('change', function() {
            const opzione = this.selectedOptions[0];
            const titoloSuggerito = opzione ? opzione.dataset.titolo : '';
            const durataSuggerita = opzione ? opzione.dataset.durata : '';

            if (durataSuggerita) {
                durataCorso.value = durataSuggerita;
            }
            if (titoloSuggerito && (!titoloCorso.value || titoloCorso.value === titoloCompilatoAutomaticamente)) {
                titoloCorso.value = titoloSuggerito;
                titoloCompilatoAutomaticamente = titoloSuggerito;
            }
        });
    }
});
