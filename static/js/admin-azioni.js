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
            '#admin-agenda': 'agenda',
            '#admin-richieste': 'richieste',
            '#admin-corsi': 'corsi',
            '#admin-aziende': 'aziende',
            '#admin-persone': 'persone',
            '#admin-attivita': 'attivita',
            '#admin-errori': 'errori',
            '#admin-impostazioni': 'impostazioni',
            '#admin-eventi': 'eventi',
            '#admin-prenotazioni': 'prenotazioni',
            '#admin-call-sonno': 'call-sonno',
        };
        const hashPerPannello = {
            agenda: '#admin-agenda',
            richieste: '#admin-richieste',
            corsi: '#admin-corsi',
            aziende: '#admin-aziende',
            persone: '#admin-persone',
            attivita: '#admin-attivita',
            errori: '#admin-errori',
            impostazioni: '#admin-impostazioni',
            eventi: '#admin-eventi',
            prenotazioni: '#admin-prenotazioni',
            'call-sonno': '#admin-call-sonno',
        };
        const haRicerca = new URLSearchParams(window.location.search).has('q');
        const pannelloIniziale = pannelliPerHash[window.location.hash] || (haRicerca ? 'persone' : 'agenda');
        mostraPannelloAdmin(pannelloIniziale);

        adminViewButtons.forEach(button => {
            button.addEventListener('click', function() {
                const target = this.dataset.adminTarget;
                mostraPannelloAdmin(target);
                window.history.replaceState(null, '', hashPerPannello[target] || '#admin-agenda');
            });
        });

        document.querySelectorAll('[data-admin-jump]').forEach(link => {
            link.addEventListener('click', function(event) {
                event.preventDefault();
                const target = this.dataset.adminJump;
                mostraPannelloAdmin(target);
                window.history.replaceState(null, '', hashPerPannello[target] || '#admin-agenda');
                document.querySelector(`[data-admin-panel="${target}"]`)?.scrollIntoView({behavior: 'smooth'});
            });
        });
    }

    document.querySelectorAll('[data-confirm]').forEach(controllo => {
        const evento = controllo.tagName.toLowerCase() === 'form' ? 'submit' : 'click';
        controllo.addEventListener(evento, function(e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

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

    const eventiMensili = document.querySelectorAll('[data-calendar-preview]');
    if (eventiMensili.length) {
        const HOVER_DELAY_MS = 1000;
        const CLOSE_DELAY_MS = 140;
        const anteprima = document.createElement('div');
        anteprima.id = 'admin-calendar-preview';
        anteprima.className = 'admin-calendar-popover';
        anteprima.setAttribute('role', 'tooltip');
        anteprima.hidden = true;
        document.body.appendChild(anteprima);

        let eventoAttivo = null;
        let timerApertura = null;
        let timerChiusura = null;

        function annullaTimer() {
            window.clearTimeout(timerApertura);
            window.clearTimeout(timerChiusura);
            timerApertura = null;
            timerChiusura = null;
        }

        function posizionaAnteprima(evento) {
            const margine = 12;
            const spazio = 12;
            const rettangolo = evento.getBoundingClientRect();
            const larghezza = Math.min(380, window.innerWidth - margine * 2);
            anteprima.style.width = `${larghezza}px`;
            anteprima.style.maxHeight = `${Math.max(180, window.innerHeight - margine * 2)}px`;

            let sinistra = rettangolo.right + spazio;
            if (sinistra + larghezza > window.innerWidth - margine) {
                sinistra = rettangolo.left - larghezza - spazio;
            }
            if (sinistra < margine) {
                sinistra = Math.min(
                    Math.max(margine, rettangolo.left),
                    window.innerWidth - larghezza - margine
                );
            }

            const altezza = anteprima.offsetHeight;
            let alto = rettangolo.top;
            if (alto + altezza > window.innerHeight - margine) {
                alto = window.innerHeight - altezza - margine;
            }
            anteprima.style.left = `${Math.round(sinistra)}px`;
            anteprima.style.top = `${Math.max(margine, Math.round(alto))}px`;
        }

        function chiudiAnteprima() {
            annullaTimer();
            if (eventoAttivo) {
                eventoAttivo.removeAttribute('aria-describedby');
            }
            eventoAttivo = null;
            anteprima.classList.remove('is-visible');
            anteprima.hidden = true;
            anteprima.replaceChildren();
        }

        function apriAnteprima(evento) {
            const modello = evento.querySelector('.admin-month-preview-template');
            if (!modello) return;
            annullaTimer();
            if (eventoAttivo && eventoAttivo !== evento) {
                eventoAttivo.removeAttribute('aria-describedby');
            }
            eventoAttivo = evento;
            eventoAttivo.setAttribute('aria-describedby', anteprima.id);
            anteprima.replaceChildren(modello.content.cloneNode(true));
            anteprima.hidden = false;
            anteprima.classList.remove('is-visible');
            posizionaAnteprima(evento);
            window.requestAnimationFrame(() => anteprima.classList.add('is-visible'));
        }

        function programmaApertura(evento) {
            if (eventoAttivo === evento) {
                window.clearTimeout(timerChiusura);
                timerChiusura = null;
                return;
            }
            chiudiAnteprima();
            timerApertura = window.setTimeout(() => apriAnteprima(evento), HOVER_DELAY_MS);
        }

        function programmaChiusura() {
            window.clearTimeout(timerApertura);
            timerApertura = null;
            window.clearTimeout(timerChiusura);
            timerChiusura = window.setTimeout(chiudiAnteprima, CLOSE_DELAY_MS);
        }

        eventiMensili.forEach(evento => {
            evento.addEventListener('pointerenter', () => programmaApertura(evento));
            evento.addEventListener('pointerleave', programmaChiusura);
            evento.addEventListener('focus', () => apriAnteprima(evento));
            evento.addEventListener('blur', programmaChiusura);
        });

        anteprima.addEventListener('pointerenter', () => window.clearTimeout(timerChiusura));
        anteprima.addEventListener('pointerleave', programmaChiusura);
        window.addEventListener('resize', chiudiAnteprima);
        window.addEventListener('scroll', event => {
            if (!(event.target instanceof Node) || !anteprima.contains(event.target)) {
                chiudiAnteprima();
            }
        }, true);
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && eventoAttivo) chiudiAnteprima();
        });
    }
});
