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
        const pannelliPerHash = {
            '#admin-corsi': 'corsi',
            '#admin-eventi': 'eventi',
            '#admin-prenotazioni': 'prenotazioni',
            '#admin-call-sonno': 'call-sonno',
        };
        const hashPerPannello = {
            corsi: '#admin-corsi',
            eventi: '#admin-eventi',
            prenotazioni: '#admin-prenotazioni',
            'call-sonno': '#admin-call-sonno',
        };
        const pannelloIniziale = pannelliPerHash[window.location.hash] || 'prenotazioni';
        mostraPannelloAdmin(pannelloIniziale);

        adminViewButtons.forEach(button => {
            button.addEventListener('click', function() {
                const target = this.dataset.adminTarget;
                mostraPannelloAdmin(target);
                window.history.replaceState(null, '', hashPerPannello[target] || '#admin-prenotazioni');
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

    const filtroTipoCorso = document.getElementById('admin-course-type-filter');
    if (filtroTipoCorso) {
        filtroTipoCorso.addEventListener('change', function() {
            this.form.submit();
        });
    }

    const personaCorsoSelect = document.getElementById('persona-corso-select');
    const campiPersonaCorso = {
        nome: document.getElementById('persona-corso-nome'),
        telefono: document.getElementById('persona-corso-telefono'),
        email: document.getElementById('persona-corso-email'),
        codiceFiscale: document.getElementById('persona-corso-codice-fiscale'),
        nomeBambino: document.getElementById('persona-corso-nome-bambino'),
        etaBambino: document.getElementById('persona-corso-eta-bambino'),
    };

    if (personaCorsoSelect) {
        personaCorsoSelect.addEventListener('change', function() {
            const opzione = this.selectedOptions[0];
            const dati = opzione ? opzione.dataset : {};

            if (!this.value) {
                Object.values(campiPersonaCorso).forEach(campo => {
                    if (campo) {
                        campo.value = '';
                    }
                });
                return;
            }

            if (campiPersonaCorso.nome) campiPersonaCorso.nome.value = dati.nome || '';
            if (campiPersonaCorso.telefono) campiPersonaCorso.telefono.value = dati.telefono || '';
            if (campiPersonaCorso.email) campiPersonaCorso.email.value = dati.email || '';
            if (campiPersonaCorso.codiceFiscale) campiPersonaCorso.codiceFiscale.value = dati.codiceFiscale || '';
            if (campiPersonaCorso.nomeBambino) campiPersonaCorso.nomeBambino.value = dati.nomeBambino || '';
            if (campiPersonaCorso.etaBambino) campiPersonaCorso.etaBambino.value = dati.etaBambino || '';
        });
    }
});
