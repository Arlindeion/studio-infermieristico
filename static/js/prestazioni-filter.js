(() => {
    const catalog = document.querySelector('[data-prestazioni-catalog]');
    if (!catalog) return;

    const search = catalog.querySelector('[data-prestazioni-search]');
    const clearButton = catalog.querySelector('[data-prestazioni-clear]');
    const status = catalog.querySelector('[data-prestazioni-status]');
    const empty = catalog.querySelector('[data-prestazioni-empty]');
    const groups = Array.from(catalog.querySelectorAll('[data-service-group]'));
    const initialOpenState = groups.map((group) => group.open);

    const normalize = (value) => value
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase('it')
        .trim();

    const update = () => {
        const query = normalize(search.value);
        let totalMatches = 0;

        groups.forEach((group, index) => {
            const rows = Array.from(group.querySelectorAll('[data-service-row]'));
            let groupMatches = 0;

            rows.forEach((row) => {
                const matches = !query || normalize(row.textContent).includes(query);
                row.hidden = !matches;
                if (matches) groupMatches += 1;
            });

            group.hidden = Boolean(query) && groupMatches === 0;
            group.querySelector('[data-service-count]').textContent = `${groupMatches} ${groupMatches === 1 ? 'prestazione' : 'prestazioni'}`;
            group.open = query ? groupMatches > 0 : initialOpenState[index];
            totalMatches += groupMatches;
        });

        clearButton.hidden = !query;
        empty.hidden = totalMatches > 0;
        status.textContent = query
            ? `${totalMatches} ${totalMatches === 1 ? 'risultato' : 'risultati'}`
            : `${totalMatches} prestazioni disponibili`;
    };

    search.addEventListener('input', update);
    clearButton.addEventListener('click', () => {
        search.value = '';
        update();
        search.focus();
    });

    update();
})();
