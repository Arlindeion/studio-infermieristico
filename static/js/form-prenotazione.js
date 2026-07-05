// Blocca le date passate nel selettore di data
document.getElementById('data').min = new Date().toISOString().split('T')[0];

const privacyCheckbox = document.querySelector('.privacy-checkbox');
const submitButton = document.getElementById('btn-invia');

function aggiornaStatoPrivacy() {
    submitButton.classList.toggle('btn-privacy-mancante', !privacyCheckbox.checked);
}

privacyCheckbox.addEventListener('change', aggiornaStatoPrivacy);
aggiornaStatoPrivacy();

// Disabilita il pulsante dopo l'invio per evitare doppi clic
document.querySelector('form.form-prenotazione').addEventListener('submit', function() {
    submitButton.disabled = true;
    submitButton.textContent = 'Invio in corso...';
});
