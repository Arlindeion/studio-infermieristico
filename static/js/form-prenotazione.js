// Blocca le date passate nel selettore di data
document.getElementById('data').min = new Date().toISOString().split('T')[0];

const privacyCheckbox = document.querySelector('.privacy-checkbox');
const submitButton = document.getElementById('btn-invia');
const bookingForm = document.querySelector('form.form-prenotazione');
const serviceInput = document.getElementById('servizio');
const serviceSummary = document.querySelector('[data-service-price-summary]');
const servicePicker = document.querySelector('[data-service-picker]');
const servicePickerToggle = servicePicker.querySelector('[data-service-picker-toggle]');
const servicePickerValue = servicePicker.querySelector('[data-service-picker-value]');
const servicePickerMenu = servicePicker.querySelector('[data-service-picker-menu]');
const servicePickerError = document.querySelector('[data-service-picker-error]');
const serviceGroups = Array.from(servicePicker.querySelectorAll('[data-service-picker-group]'));
const serviceOptions = Array.from(servicePicker.querySelectorAll('[data-service-option]'));

function chiudiCategorie(tranne = null) {
    serviceGroups.forEach(group => {
        if (group !== tranne) {
            group.classList.remove('is-open');
            group.querySelector('[data-service-category]').setAttribute('aria-expanded', 'false');
        }
    });
}

function impostaCategoriaAperta(group, isOpen) {
    chiudiCategorie(isOpen ? group : null);
    group.classList.toggle('is-open', isOpen);
    group.querySelector('[data-service-category]').setAttribute('aria-expanded', String(isOpen));
}

function impostaMenuAperto(isOpen) {
    servicePickerMenu.hidden = !isOpen;
    servicePickerToggle.setAttribute('aria-expanded', String(isOpen));
    servicePicker.classList.toggle('is-open', isOpen);
    if (!isOpen) {
        chiudiCategorie();
    }
}

function aggiornaRiepilogoPrestazione(selectedOption = null) {
    const hasSelection = Boolean(selectedOption && serviceInput.value);

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

function selezionaPrestazione(option) {
    serviceInput.value = option.dataset.serviceName;
    servicePickerValue.textContent = option.dataset.serviceName;
    servicePickerToggle.classList.add('has-selection');
    serviceOptions.forEach(item => item.classList.toggle('is-selected', item === option));
    servicePickerError.hidden = true;
    aggiornaRiepilogoPrestazione(option);
    impostaMenuAperto(false);
    servicePickerToggle.focus();
}

function aggiornaStatoPrivacy() {
    submitButton.classList.toggle('btn-privacy-mancante', !privacyCheckbox.checked);
}

privacyCheckbox.addEventListener('change', aggiornaStatoPrivacy);
aggiornaStatoPrivacy();

servicePickerToggle.addEventListener('click', function() {
    impostaMenuAperto(servicePickerMenu.hidden);
});

serviceGroups.forEach(group => {
    const categoryButton = group.querySelector('[data-service-category]');

    group.addEventListener('mouseenter', function() {
        impostaCategoriaAperta(group, true);
    });
    group.addEventListener('mouseleave', function() {
        if (!group.contains(document.activeElement)) {
            impostaCategoriaAperta(group, false);
        }
    });
    categoryButton.addEventListener('focus', function() {
        impostaCategoriaAperta(group, true);
    });
    categoryButton.addEventListener('click', function() {
        impostaCategoriaAperta(group, true);
    });
});

serviceOptions.forEach(option => {
    option.addEventListener('click', function() {
        selezionaPrestazione(option);
    });
});

document.addEventListener('click', function(event) {
    if (!servicePicker.contains(event.target)) {
        impostaMenuAperto(false);
    }
});

servicePicker.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        impostaMenuAperto(false);
        servicePickerToggle.focus();
    }
});

const initialServiceOption = serviceOptions.find(option => option.dataset.serviceName === serviceInput.value);
if (initialServiceOption) {
    servicePickerValue.textContent = initialServiceOption.dataset.serviceName;
    servicePickerToggle.classList.add('has-selection');
    initialServiceOption.classList.add('is-selected');
    aggiornaRiepilogoPrestazione(initialServiceOption);
} else {
    aggiornaRiepilogoPrestazione();
}

// Disabilita il pulsante dopo l'invio per evitare doppi clic
bookingForm.addEventListener('submit', function(event) {
    if (!serviceInput.value) {
        event.preventDefault();
        servicePickerError.hidden = false;
        impostaMenuAperto(true);
        servicePickerToggle.focus();
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Invio in corso...';
});
