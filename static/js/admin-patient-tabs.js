document.addEventListener('DOMContentLoaded', function() {
    const shell = document.querySelector('[data-patient-tabs]');
    if (!shell) return;

    const tabs = Array.from(shell.querySelectorAll('[data-patient-tab]'));
    const panels = Array.from(shell.querySelectorAll('[data-patient-panel]'));

    function openTab(name, updateHash = true) {
        const selected = tabs.find(tab => tab.dataset.patientTab === name);
        if (!selected) return;

        tabs.forEach(tab => {
            const active = tab === selected;
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
            tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach(panel => {
            const active = panel.dataset.patientPanel === name;
            panel.hidden = !active;
            panel.classList.toggle('is-active', active);
        });
        if (updateHash) {
            window.history.replaceState(null, '', `#patient-${name}`);
        }
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => openTab(tab.dataset.patientTab));
        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            let nextIndex = index;
            if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
            if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
            if (event.key === 'Home') nextIndex = 0;
            if (event.key === 'End') nextIndex = tabs.length - 1;
            tabs[nextIndex].focus();
            openTab(tabs[nextIndex].dataset.patientTab);
        });
    });

    shell.querySelectorAll('[data-open-patient-tab]').forEach(control => {
        control.addEventListener('click', () => {
            openTab(control.dataset.openPatientTab);
            tabs.find(tab => tab.dataset.patientTab === control.dataset.openPatientTab)?.focus();
        });
    });

    const requested = window.location.hash.replace('#patient-', '');
    openTab(tabs.some(tab => tab.dataset.patientTab === requested) ? requested : 'overview', false);
});
