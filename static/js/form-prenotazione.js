// Blocca le date passate nel selettore di data
document.getElementById('data').min = new Date().toISOString().split('T')[0];

const privacyCheckbox = document.querySelector('.privacy-checkbox');
const submitButton = document.getElementById('btn-invia');
const serviceCategorySelect = document.getElementById('categoria-servizio');
const serviceSelect = document.getElementById('servizio');
const serviceSummary = document.querySelector('[data-service-price-summary]');

function aggiornaMenuPrestazioni() {
    if (!serviceCategorySelect || !serviceSelect) {
        return;
    }

    const selectedCategory = serviceCategorySelect.value;
    const selectedOption = serviceSelect.selectedOptions[0];
    const selectionMatchesCategory = Boolean(
        selectedOption
        && selectedOption.value
        && selectedOption.dataset.categorySlug === selectedCategory
    );

    Array.from(serviceSelect.options).forEach((option, index) => {
        if (index === 0) {
            option.textContent = selectedCategory
                ? 'Seleziona una prestazione'
                : 'Prima scegli una categoria';
            return;
        }

        const belongsToCategory = option.dataset.categorySlug === selectedCategory;
        option.hidden = !belongsToCategory;
        option.disabled = !belongsToCategory;
    });

    serviceSelect.disabled = !selectedCategory;
    if (!selectionMatchesCategory) {
        serviceSelect.value = '';
    }
}

function aggiornaRiepilogoPrestazione() {
    if (!serviceSelect || !serviceSummary) {
        return;
    }

    const selectedOption = serviceSelect.selectedOptions[0];
    const hasSelection = Boolean(selectedOption && selectedOption.value);
    const serviceName = serviceSummary.querySelector('[data-service-summary-name]');
    const serviceCategory = serviceSummary.querySelector('[data-service-summary-category]');
    const servicePrice = serviceSummary.querySelector('[data-service-summary-price]');

    serviceSummary.classList.toggle('is-selected', hasSelection);
    serviceName.textContent = hasSelection
        ? selectedOption.dataset.serviceName
        : 'Nessuna prestazione selezionata';
    serviceCategory.textContent = hasSelection
        ? selectedOption.dataset.category
        : 'Scegli categoria e prestazione per vedere il riepilogo.';
    servicePrice.textContent = hasSelection ? selectedOption.dataset.price : '—';
}

function aggiornaStatoPrivacy() {
    submitButton.classList.toggle('btn-privacy-mancante', !privacyCheckbox.checked);
}

privacyCheckbox.addEventListener('change', aggiornaStatoPrivacy);
aggiornaStatoPrivacy();

serviceCategorySelect.addEventListener('change', function() {
    aggiornaMenuPrestazioni();
    aggiornaRiepilogoPrestazione();
});
serviceSelect.addEventListener('change', aggiornaRiepilogoPrestazione);
aggiornaMenuPrestazioni();
aggiornaRiepilogoPrestazione();

// Disabilita il pulsante dopo l'invio per evitare doppi clic
document.querySelector('form.form-prenotazione').addEventListener('submit', function() {
    submitButton.disabled = true;
    submitButton.textContent = 'Invio in corso...';
});
