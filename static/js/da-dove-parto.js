(() => {
    const quiz = document.querySelector('[data-orientation-quiz]');
    if (!quiz) return;

    const percorsi = {
        nascita: {title: 'Accompagnamento alla nascita', copy: 'Un percorso per prepararsi insieme, conoscere i passaggi e arrivare con domande più chiare.', href: '/corso-accompagnamento-nascita', label: 'Scopri il percorso nascita'},
        prestazioni: {title: 'Prestazioni infermieristiche', copy: 'Consulta le prestazioni disponibili in studio e scegli poi servizio, giorno e orario.', href: '/prestazioni-infermieristiche', label: 'Consulta le prestazioni'},
        azienda: {title: 'Formazione per aziende e gruppi', copy: 'Usa il modulo organizzativo: raccoglie contesto, partecipanti, sede e periodo prima della proposta.', href: '/aziende-e-gruppi', label: 'Avvia una richiesta organizzativa'},
        sicurezza: {title: 'Corsi di sicurezza e primo intervento', copy: 'Confronta disostruzione pediatrica, tagli sicuri e BLSD, poi verifica le prossime edizioni.', href: '/iscrizione-corsi', label: 'Confronta i corsi'},
        sonno: {title: 'Consulenza del sonno 0–12 mesi', copy: 'Leggi come funziona il primo confronto online prima di scegliere un orario disponibile.', href: '/consulenze-online', label: 'Scopri la consulenza'},
        laboratori: {title: 'Laboratori per l’infanzia', copy: 'Esplora le attività dedicate ad alimentazione, gioco e sviluppo e controlla le prossime date.', href: '/iscrizione-corsi/laboratorio-infanzia', label: 'Scopri i laboratori'},
        dubbi: {title: 'Confronta prima di scegliere', copy: 'Le domande frequenti chiariscono differenze, prenotazioni e contatti senza obbligarti a inviare una richiesta.', href: '/faq', label: 'Apri le domande frequenti'}
    };

    const steps = [...quiz.querySelectorAll('[data-quiz-step]')];
    const resultPanel = quiz.querySelector('[data-quiz-result-panel]');
    const progress = quiz.querySelector('[data-quiz-progress]');
    const count = quiz.querySelector('[data-quiz-step-count]');
    const title = quiz.querySelector('[data-result-title]');
    const copy = quiz.querySelector('[data-result-copy]');
    const link = quiz.querySelector('[data-result-link]');

    const showStep = (name) => {
        steps.forEach((step) => {
            const active = step.dataset.quizStep === name;
            step.hidden = !active;
            step.classList.toggle('is-active', active);
        });
        resultPanel.hidden = true;
        progress.style.width = name === 'start' ? '50%' : '75%';
        count.textContent = name === 'start' ? 'Passaggio 1 di 2' : 'Passaggio 2 di 2';
        const activeHeading = quiz.querySelector('[data-quiz-step]:not([hidden]) h2');
        if (activeHeading) activeHeading.focus({preventScroll: true});
    };

    const showResult = (key) => {
        const result = percorsi[key];
        if (!result) return;
        steps.forEach((step) => { step.hidden = true; });
        title.textContent = result.title;
        copy.textContent = result.copy;
        link.href = result.href;
        link.textContent = result.label;
        resultPanel.hidden = false;
        progress.style.width = '100%';
        count.textContent = 'Orientamento completato';
        title.setAttribute('tabindex', '-1');
        title.focus({preventScroll: true});
    };

    quiz.addEventListener('click', (event) => {
        const next = event.target.closest('[data-quiz-next]');
        const result = event.target.closest('[data-quiz-result]');
        if (next) showStep(next.dataset.quizNext);
        if (result) showResult(result.dataset.quizResult);
        if (event.target.closest('[data-quiz-back]')) showStep('start');
        if (event.target.closest('[data-quiz-reset]')) showStep('start');
    });

    showStep('start');
})();
