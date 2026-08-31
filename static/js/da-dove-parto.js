(() => {
    const quiz = document.querySelector('[data-orientation-quiz]');
    if (!quiz) return;

    const percorsi = {
        nascita: {title: 'Accompagnamento alla nascita', copy: 'Un percorso per prepararsi insieme, conoscere i passaggi e arrivare con domande più chiare.', href: '/corso-accompagnamento-nascita', label: 'Scopri il percorso nascita'},
        prestazioni: {title: 'Prestazioni infermieristiche', copy: 'Consulta le prestazioni disponibili in studio e scegli poi servizio, giorno e orario.', href: '/prestazioni-infermieristiche', label: 'Consulta le prestazioni'},
        azienda: {title: 'Formazione per aziende e gruppi', copy: 'Usa il modulo organizzativo: raccoglie contesto, partecipanti, sede e periodo prima della proposta.', href: '/aziende-e-gruppi', label: 'Avvia una richiesta organizzativa'},
        sicurezza: {title: 'Corsi di sicurezza e primo intervento', copy: 'Confronta disostruzione pediatrica, tagli sicuri e BLSD, poi verifica le prossime edizioni.', href: '/iscrizione-corsi', label: 'Confronta i corsi'},
        sonno: {title: 'Consulenza del sonno', copy: 'Leggi come funziona il primo confronto online prima di scegliere un orario disponibile.', href: '/consulenze-online', label: 'Scopri la consulenza'},
        laboratori: {title: 'Laboratori per l’infanzia', copy: 'Esplora le attività dedicate ad alimentazione, gioco e sviluppo e controlla le prossime date.', href: '/iscrizione-corsi/laboratorio-infanzia', label: 'Scopri i laboratori'},
        dubbi: {title: 'Confronta prima di scegliere', copy: 'Le domande frequenti chiariscono differenze, prenotazioni e contatti senza obbligarti a inviare una richiesta.', href: '/faq', label: 'Apri le domande frequenti'}
    };

    const stage = quiz.querySelector('[data-quiz-stage]');
    const steps = [...quiz.querySelectorAll('[data-quiz-step]')];
    const resultPanel = quiz.querySelector('[data-quiz-result-panel]');
    const panels = [...steps, resultPanel];
    const progress = quiz.querySelector('[data-quiz-progress]');
    const count = quiz.querySelector('[data-quiz-step-count]');
    const title = quiz.querySelector('[data-result-title]');
    const copy = quiz.querySelector('[data-result-copy]');
    const link = quiz.querySelector('[data-result-link]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const transitionDuration = 620;
    let activePanel = null;
    let transitionRunning = false;
    let transitionTimer = null;

    const focusPanel = (panel, target = null) => {
        const heading = target || panel.querySelector('h2');
        if (heading) heading.focus({preventScroll: true});
    };

    const transitionTo = (nextPanel, direction, focusTarget = null) => {
        if (!nextPanel || transitionRunning || nextPanel === activePanel) return;
        const previousPanel = activePanel;

        panels.forEach((panel) => {
            if (panel !== previousPanel && panel !== nextPanel) panel.hidden = true;
        });
        nextPanel.hidden = false;
        nextPanel.removeAttribute('aria-hidden');
        nextPanel.inert = false;

        const finish = () => {
            window.clearTimeout(transitionTimer);
            nextPanel.removeEventListener('animationend', finish);
            nextPanel.classList.remove('is-entering-forward', 'is-entering-backward');
            nextPanel.classList.add('is-active');
            if (previousPanel) {
                previousPanel.hidden = true;
                previousPanel.inert = false;
                previousPanel.removeAttribute('aria-hidden');
                previousPanel.classList.remove('is-active');
            }
            stage.style.removeProperty('--orientation-stage-height');
            activePanel = nextPanel;
            transitionRunning = false;
            focusPanel(nextPanel, focusTarget);
        };

        if (!previousPanel || reducedMotion.matches || direction === 'none') {
            if (previousPanel) {
                previousPanel.hidden = true;
                previousPanel.classList.remove('is-active');
            }
            activePanel = nextPanel;
            nextPanel.classList.add('is-active');
            focusPanel(nextPanel, focusTarget);
            return;
        }

        transitionRunning = true;
        previousPanel.setAttribute('aria-hidden', 'true');
        previousPanel.inert = true;
        stage.style.setProperty(
            '--orientation-stage-height',
            `${Math.max(previousPanel.offsetHeight, nextPanel.offsetHeight)}px`
        );
        nextPanel.classList.add(`is-entering-${direction}`);
        nextPanel.addEventListener('animationend', finish, {once: true});
        transitionTimer = window.setTimeout(finish, transitionDuration + 100);
    };

    const showStep = (name, direction = 'forward') => {
        const nextPanel = steps.find((step) => step.dataset.quizStep === name);
        if (!nextPanel) return;
        progress.style.width = name === 'start' ? '50%' : '75%';
        count.textContent = name === 'start' ? 'Passaggio 1 di 2' : 'Passaggio 2 di 2';
        transitionTo(nextPanel, direction);
    };

    const showResult = (key) => {
        const result = percorsi[key];
        if (!result || transitionRunning) return;
        title.textContent = result.title;
        copy.textContent = result.copy;
        link.href = result.href;
        link.textContent = result.label;
        progress.style.width = '100%';
        count.textContent = 'Orientamento completato';
        title.setAttribute('tabindex', '-1');
        transitionTo(resultPanel, 'forward', title);
    };

    quiz.addEventListener('click', (event) => {
        if (transitionRunning) return;
        const next = event.target.closest('[data-quiz-next]');
        const result = event.target.closest('[data-quiz-result]');
        if (next) showStep(next.dataset.quizNext, 'forward');
        if (result) showResult(result.dataset.quizResult);
        if (event.target.closest('[data-quiz-back]')) showStep('start', 'backward');
        if (event.target.closest('[data-quiz-reset]')) showStep('start', 'backward');
    });

    showStep('start', 'none');
})();
