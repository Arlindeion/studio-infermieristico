// Azioni admin: conferma le azioni per appuntamenti e corsi
document.addEventListener('DOMContentLoaded', function() {
    const modalConflittiCalendar = document.querySelector('[data-calendar-conflict-modal][data-open-on-load]');
    if (modalConflittiCalendar && typeof modalConflittiCalendar.showModal === 'function') {
        modalConflittiCalendar.showModal();
    }

    const adminViewButtons = document.querySelectorAll('[data-admin-target]');
    const adminPanels = document.querySelectorAll('[data-admin-panel]');

    function mostraPannelloAdmin(nomePannello) {
        adminPanels.forEach(panel => {
            panel.classList.toggle('is-hidden', panel.dataset.adminPanel !== nomePannello);
        });
        adminViewButtons.forEach(button => {
            const attivo = button.dataset.adminTarget === nomePannello;
            button.classList.toggle('attivo', attivo);
            if (attivo) {
                button.setAttribute('aria-current', 'page');
            } else {
                button.removeAttribute('aria-current');
            }
        });
    }

    if (adminViewButtons.length && adminPanels.length) {
        const pannelliPerHash = {
            '#admin-agenda': 'agenda',
            '#admin-richieste': 'richieste',
            '#admin-corsi': 'corsi',
            '#admin-nuovo-corso': 'nuovo-corso',
            '#admin-aziende': 'aziende',
            '#admin-pazienti': 'pazienti',
            '#admin-persone': 'pazienti',
            '#admin-attivita': 'attivita',
            '#admin-errori': 'errori',
            '#admin-impostazioni': 'impostazioni',
            '#admin-eventi': 'eventi',
            '#admin-prenotazioni': 'prenotazioni',
            '#admin-archivio-corsi': 'archivio-corsi',
            '#admin-call-sonno': 'call-sonno',
        };
        const hashPerPannello = {
            agenda: '#admin-agenda',
            richieste: '#admin-richieste',
            corsi: '#admin-corsi',
            'nuovo-corso': '#admin-nuovo-corso',
            aziende: '#admin-aziende',
            pazienti: '#admin-pazienti',
            attivita: '#admin-attivita',
            errori: '#admin-errori',
            impostazioni: '#admin-impostazioni',
            eventi: '#admin-eventi',
            prenotazioni: '#admin-prenotazioni',
            'archivio-corsi': '#admin-archivio-corsi',
            'call-sonno': '#admin-call-sonno',
        };
        const haRicerca = new URLSearchParams(window.location.search).has('q');
        const pannelloIniziale = pannelliPerHash[window.location.hash] || (haRicerca ? 'pazienti' : 'agenda');
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

    const selettoreMeseAdmin = document.querySelector('[data-submit-on-change]');
    if (selettoreMeseAdmin) {
        selettoreMeseAdmin.addEventListener('change', function() {
            if (!this.value || !this.form) return;
            if (typeof this.form.requestSubmit === 'function') {
                this.form.requestSubmit();
            } else {
                this.form.submit();
            }
        });
    }

    const personaCorsoSelect = document.getElementById('persona-corso-select');
    const corsoManualeSelect = document.getElementById('manual-course-id');
    const tipoRichiestaManuale = document.getElementById('manual-request-type');
    const opzioneOpenDayManuale = document.getElementById('manual-request-type-open-day');

    function aggiornaDisponibilitaOpenDay() {
        if (!corsoManualeSelect || !tipoRichiestaManuale || !opzioneOpenDayManuale) return;
        const corsoSelezionato = corsoManualeSelect.selectedOptions[0];
        const openDayDisponibile = corsoSelezionato?.dataset.corsoTipo === 'accompagnamento-nascita';
        opzioneOpenDayManuale.hidden = !openDayDisponibile;
        opzioneOpenDayManuale.disabled = !openDayDisponibile;
        if (!openDayDisponibile && tipoRichiestaManuale.value === 'open_day') {
            tipoRichiestaManuale.value = 'richiesta_iscrizione';
        }
    }

    if (corsoManualeSelect && tipoRichiestaManuale && opzioneOpenDayManuale) {
        corsoManualeSelect.addEventListener('change', aggiornaDisponibilitaOpenDay);
        aggiornaDisponibilitaOpenDay();
    }

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


    const nuovoAppuntamentoForm = document.getElementById('admin-new-appointment-form');
    if (nuovoAppuntamentoForm) {
        const messaggioModulo = nuovoAppuntamentoForm.querySelector('.admin-inline-form-message');
        const confermaContatti = nuovoAppuntamentoForm.elements.confirm_missing_contacts;
        const selezionePersona = document.getElementById('admin-appointment-person');
        const dataAppuntamento = document.getElementById('admin-appointment-date');
        const apriCalendario = nuovoAppuntamentoForm.querySelector('[data-open-date-picker]');
        const pulsanteInvio = nuovoAppuntamentoForm.querySelector('button[type="submit"]');

        function mostraErroreModulo(messaggio) {
            messaggioModulo.textContent = messaggio;
            messaggioModulo.hidden = false;
            messaggioModulo.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        }

        function nascondiErroreModulo() {
            messaggioModulo.textContent = '';
            messaggioModulo.hidden = true;
        }

        if (selezionePersona) {
            selezionePersona.addEventListener('change', function() {
                const persona = this.selectedOptions[0]?.dataset || {};
                if (!this.value) return;
                nuovoAppuntamentoForm.elements.nome.value = persona.nome || '';
                nuovoAppuntamentoForm.elements.telefono.value = persona.telefono || '';
                nuovoAppuntamentoForm.elements.email.value = persona.email || '';
                confermaContatti.value = '0';
                nascondiErroreModulo();
            });
        }

        if (apriCalendario && dataAppuntamento) {
            apriCalendario.addEventListener('click', function() {
                dataAppuntamento.focus();
                if (typeof dataAppuntamento.showPicker === 'function') {
                    dataAppuntamento.showPicker();
                }
            });
        }

        async function inviaNuovoAppuntamento(contattiMancantiConfermati = false) {
            nascondiErroreModulo();
            confermaContatti.value = contattiMancantiConfermati ? '1' : '0';

            if (!nuovoAppuntamentoForm.checkValidity()) {
                nuovoAppuntamentoForm.reportValidity();
                return;
            }

            const mancanti = [];
            if (!nuovoAppuntamentoForm.elements.telefono.value.trim()) mancanti.push('telefono');
            if (!nuovoAppuntamentoForm.elements.email.value.trim()) mancanti.push('email');
            if (mancanti.length && !contattiMancantiConfermati) {
                const confermato = window.confirm(
                    `Mancano ${mancanti.join(' e ')}. Vuoi creare comunque l’appuntamento?`
                );
                if (!confermato) return;
                return inviaNuovoAppuntamento(true);
            }

            pulsanteInvio.disabled = true;
            pulsanteInvio.setAttribute('aria-busy', 'true');
            try {
                const risposta = await fetch(nuovoAppuntamentoForm.action, {
                    method: 'POST',
                    body: new FormData(nuovoAppuntamentoForm),
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                const risultato = await risposta.json();
                if (!risposta.ok) {
                    if (risultato.requires_missing_contacts_confirmation && !contattiMancantiConfermati) {
                        const confermato = window.confirm(`${risultato.message} Vuoi procedere?`);
                        if (confermato) return inviaNuovoAppuntamento(true);
                        return;
                    }
                    mostraErroreModulo(risultato.message || 'Non è stato possibile creare l’appuntamento.');
                    return;
                }
                window.location.assign(risultato.redirect);
            } catch (errore) {
                mostraErroreModulo('Connessione interrotta: i dati sono ancora nel modulo. Riprova.');
            } finally {
                pulsanteInvio.disabled = false;
                pulsanteInvio.removeAttribute('aria-busy');
            }
        }

        nuovoAppuntamentoForm.addEventListener('input', function() {
            confermaContatti.value = '0';
            nascondiErroreModulo();
        });
        nuovoAppuntamentoForm.addEventListener('submit', function(event) {
            event.preventDefault();
            inviaNuovoAppuntamento(false);
        });
    }

    const agendaSettimanale = document.querySelector('[data-admin-week-grid]');
    const dialogSpostamento = document.querySelector('[data-drag-move-dialog]');
    if (agendaSettimanale && dialogSpostamento) {
        const inizioMinuti = Number(agendaSettimanale.dataset.weekStartMinute || 420);
        const fineMinuti = Number(agendaSettimanale.dataset.weekEndMinute || 1320);
        const snapMinuti = Number(agendaSettimanale.dataset.weekSnapMinute || 15);
        const teleGiorno = [...agendaSettimanale.querySelectorAll('[data-week-day]')];
        const eventi = [...agendaSettimanale.querySelectorAll('[data-week-event]')];
        const csrf = dialogSpostamento.querySelector('[data-drag-csrf]');
        const bottoneMail = dialogSpostamento.querySelector('[data-drag-choice="mail"]');
        const notaMail = dialogSpostamento.querySelector('[data-drag-mail-note]');
        const anteprima = document.createElement('div');
        anteprima.className = 'admin-week-drop-preview';
        anteprima.hidden = true;
        let trascinato = null;
        let origine = null;
        let proposta = null;
        let attesaConferma = false;

        function minutiDaOra(valore) {
            const parti = String(valore || '').split(':').map(Number);
            if (parti.length !== 2 || parti.some(Number.isNaN)) return null;
            return parti[0] * 60 + parti[1];
        }

        function oraDaMinuti(minuti) {
            const ore = Math.floor(minuti / 60);
            const resto = minuti % 60;
            return `${String(ore).padStart(2, '0')}:${String(resto).padStart(2, '0')}`;
        }

        function durataEvento(evento) {
            const start = minutiDaOra(evento.dataset.eventStart);
            const end = minutiDaOra(evento.dataset.eventEnd);
            if (start === null || end === null) return 30;
            return Math.max(15, end >= start ? end - start : 1440 - start + end);
        }

        function geometriaEvento(ora, durata) {
            const start = minutiDaOra(ora);
            if (start === null) return null;
            const totale = fineMinuti - inizioMinuti;
            const startVisibile = Math.max(inizioMinuti, Math.min(start, fineMinuti));
            const endVisibile = Math.max(inizioMinuti, Math.min(start + durata, fineMinuti));
            return {
                top: `${((startVisibile - inizioMinuti) / totale) * 100}%`,
                height: `${Math.max(((endVisibile - startVisibile) / totale) * 100, 1.8)}%`,
                hidden: endVisibile <= inizioMinuti || startVisibile >= fineMinuti,
            };
        }

        function posizionaEvento(evento, ora = evento.dataset.eventStart) {
            const geometria = geometriaEvento(ora, durataEvento(evento));
            if (!geometria) return;
            evento.style.top = geometria.top;
            evento.style.height = geometria.height;
            evento.hidden = geometria.hidden;
        }

        function formattaData(dataIso) {
            const [anno, mese, giorno] = dataIso.split('-');
            return `${giorno}/${mese}/${anno}`;
        }

        function rimuoviAnteprima() {
            anteprima.remove();
            anteprima.hidden = true;
        }

        function azzeraTrascinamento() {
            if (trascinato) {
                trascinato.classList.remove('is-dragging', 'is-pending-move');
            }
            rimuoviAnteprima();
            trascinato = null;
            origine = null;
            proposta = null;
            attesaConferma = false;
        }

        function aggiornaAnteprima(canvas, clientY) {
            if (!trascinato) return;
            const rect = canvas.getBoundingClientRect();
            const durata = durataEvento(trascinato);
            const percentuale = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
            let minuti = inizioMinuti + percentuale * (fineMinuti - inizioMinuti);
            minuti = Math.round(minuti / snapMinuti) * snapMinuti;
            minuti = Math.max(inizioMinuti, Math.min(minuti, fineMinuti - durata));
            const ora = oraDaMinuti(minuti);
            const geometria = geometriaEvento(ora, durata);
            if (!geometria) return;
            if (anteprima.parentElement !== canvas) canvas.appendChild(anteprima);
            anteprima.hidden = false;
            anteprima.style.top = geometria.top;
            anteprima.style.height = geometria.height;
            anteprima.textContent = ora;
            proposta = {data: canvas.dataset.weekDay, ora};
        }

        function apriDialog() {
            if (!trascinato || !origine || !proposta) return;
            dialogSpostamento.querySelector('[data-drag-appointment-title]').textContent =
                trascinato.querySelector('strong')?.textContent || 'Appuntamento';
            dialogSpostamento.querySelector('[data-drag-from]').textContent =
                `${formattaData(origine.data)} · ${origine.ora}`;
            dialogSpostamento.querySelector('[data-drag-to]').textContent =
                `${formattaData(proposta.data)} · ${proposta.ora}`;
            const haEmail = trascinato.dataset.hasEmail === '1';
            bottoneMail.disabled = !haEmail;
            notaMail.hidden = haEmail;
            notaMail.textContent = haEmail
                ? ''
                : 'Il paziente non ha un indirizzo email registrato: puoi confermare solo senza mail.';
            trascinato.classList.add('is-pending-move');
            dialogSpostamento.showModal();
        }

        async function salvaSpostamento(inviaMail) {
            if (!trascinato || !origine || !proposta) return;
            const appuntamento = trascinato;
            const origineRichiesta = {...origine};
            const propostaRichiesta = {...proposta};
            const durata = durataEvento(appuntamento);
            const formData = new FormData();
            formData.set('_csrf_token', csrf?.value || '');
            formData.set('data_originale', origineRichiesta.data);
            formData.set('ora_originale', origineRichiesta.ora);
            formData.set('data', propostaRichiesta.data);
            formData.set('ora', propostaRichiesta.ora);
            formData.set('invia_email', inviaMail ? '1' : '0');
            const azioni = [...dialogSpostamento.querySelectorAll('[data-drag-choice]')];
            azioni.forEach(button => { button.disabled = true; });

            try {
                const risposta = await fetch(`/admin/appuntamento/${appuntamento.dataset.eventId}/sposta-agenda`, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                const risultato = await risposta.json();
                if (!risposta.ok || !risultato.ok) {
                    if (risultato.requires_without_email) {
                        bottoneMail.disabled = true;
                        notaMail.hidden = false;
                        notaMail.textContent = risultato.message;
                        return;
                    }
                    window.alert(risultato.message || 'Spostamento non riuscito.');
                    dialogSpostamento.close();
                    azzeraTrascinamento();
                    return;
                }

                const canvasDestinazione = teleGiorno.find(
                    canvas => canvas.dataset.weekDay === risultato.data
                );
                if (!canvasDestinazione) {
                    window.location.reload();
                    return;
                }
                const nuovaFine = minutiDaOra(risultato.ora) + durata;
                appuntamento.dataset.eventDate = risultato.data;
                appuntamento.dataset.eventStart = risultato.ora;
                appuntamento.dataset.eventEnd = oraDaMinuti(nuovaFine % 1440);
                canvasDestinazione.appendChild(appuntamento);
                posizionaEvento(appuntamento);
                const etichettaOra = appuntamento.querySelector('[data-week-event-time]');
                if (etichettaOra) {
                    etichettaOra.textContent = `${risultato.ora}–${appuntamento.dataset.eventEnd}`;
                }
                dialogSpostamento.close();
                azzeraTrascinamento();
                if (!risultato.calendar_ok || (inviaMail && risultato.email_sent === false)) {
                    window.alert(risultato.message);
                }
            } catch (_errore) {
                window.alert('Connessione interrotta: lo spostamento non è stato confermato.');
                dialogSpostamento.close();
                azzeraTrascinamento();
            } finally {
                azioni.forEach(button => { button.disabled = false; });
                bottoneMail.disabled = appuntamento.dataset.hasEmail !== '1';
            }
        }

        eventi.forEach(posizionaEvento);
        agendaSettimanale.querySelectorAll('[data-week-appointment]').forEach(evento => {
            evento.addEventListener('dragstart', function(event) {
                trascinato = this;
                origine = {
                    canvas: this.parentElement,
                    data: this.dataset.eventDate,
                    ora: this.dataset.eventStart,
                    fine: this.dataset.eventEnd,
                };
                proposta = {data: origine.data, ora: origine.ora};
                attesaConferma = false;
                this.classList.add('is-dragging');
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', this.dataset.eventId || 'appuntamento');
            });
            evento.addEventListener('dragend', function() {
                this.classList.remove('is-dragging');
                if (!attesaConferma) azzeraTrascinamento();
            });
        });

        teleGiorno.forEach(canvas => {
            canvas.addEventListener('dragover', function(event) {
                if (!trascinato) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                aggiornaAnteprima(this, event.clientY);
            });
            canvas.addEventListener('drop', function(event) {
                if (!trascinato) return;
                event.preventDefault();
                aggiornaAnteprima(this, event.clientY);
                if (!proposta || (proposta.data === origine.data && proposta.ora === origine.ora)) {
                    azzeraTrascinamento();
                    return;
                }
                attesaConferma = true;
                trascinato.classList.remove('is-dragging');
                apriDialog();
            });
        });

        dialogSpostamento.querySelector('[data-drag-choice="cancel"]').addEventListener('click', function() {
            dialogSpostamento.close();
            azzeraTrascinamento();
        });
        bottoneMail.addEventListener('click', () => salvaSpostamento(true));
        dialogSpostamento.querySelector('[data-drag-choice="no-mail"]').addEventListener('click', () => salvaSpostamento(false));
        dialogSpostamento.addEventListener('cancel', function(event) {
            event.preventDefault();
            dialogSpostamento.close();
            azzeraTrascinamento();
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
