// Blocca le date passate nel selettore di data
document.getElementById('data').min = new Date().toISOString().split('T')[0];

// Disabilita il pulsante dopo l'invio per evitare doppi clic
document.querySelector('form.form-prenotazione').addEventListener('submit', function() {
    const btn = document.getElementById('btn-invia');
    btn.disabled = true;
    btn.textContent = 'Invio in corso...';
});