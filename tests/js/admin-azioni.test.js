const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const script = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/admin-azioni.js'),
    'utf8'
);

test('apre il modal Calendar soltanto quando il server lo richiede', () => {
    assert.match(script, /\[data-calendar-conflict-modal\]\[data-open-on-load\]/);
    assert.match(script, /typeof modalConflittiCalendar\.showModal === 'function'/);
    assert.match(script, /modalConflittiCalendar\.showModal\(\)/);
});

test('registra una sola volta i collegamenti rapidi tra sezioni admin', () => {
    const registrazioni = script.match(/querySelectorAll\('\[data-admin-jump\]'\)/g) || [];
    const funzioneCambioPannello = script.match(/function mostraPannelloAdmin[\s\S]*?\n    \}\n\n    if/);

    assert.equal(registrazioni.length, 1);
    assert.ok(funzioneCambioPannello);
    assert.doesNotMatch(funzioneCambioPannello[0], /data-admin-jump|addEventListener/);
});

test('apre fuori dal calendario i dettagli dopo un secondo continuato', () => {
    assert.match(script, /const HOVER_DELAY_MS = 1000;/);
    assert.match(script, /document\.body\.appendChild\(anteprima\)/);
    assert.match(script, /setTimeout\(\(\) => apriAnteprima\(evento\), HOVER_DELAY_MS\)/);
    assert.match(script, /addEventListener\('pointerenter'/);
    assert.match(script, /addEventListener\('pointerleave'/);
});

test('rende l’anteprima mensile utilizzabile anche da tastiera', () => {
    assert.match(script, /addEventListener\('focus', \(\) => apriAnteprima\(evento\)\)/);
    assert.match(script, /event\.key === 'Escape'/);
    assert.match(script, /setAttribute\('aria-describedby', anteprima\.id\)/);
});

test('conferma i contatti mancanti senza svuotare il modulo', () => {
    assert.match(script, /document\.getElementById\('admin-new-appointment-form'\)/);
    assert.match(script, /Mancano \$\{mancanti\.join\(' e '\)\}/);
    assert.match(script, /window\.confirm/);
    assert.match(script, /confirm_missing_contacts/);
    assert.match(script, /new FormData\(nuovoAppuntamentoForm\)/);
    assert.match(script, /i dati sono ancora nel modulo/);
    assert.doesNotMatch(script, /nuovoAppuntamentoForm\.reset\(/);
});

test('apre il calendario e usa menu distinti per ore e minuti', () => {
    assert.match(script, /document\.getElementById\('admin-appointment-date'\)/);
    assert.match(script, /typeof dataAppuntamento\.showPicker === 'function'/);
    assert.match(script, /dataAppuntamento\.showPicker\(\)/);
});

test('invia subito il mese selezionato senza pulsante aggiuntivo', () => {
    assert.match(script, /querySelector\('\[data-submit-on-change\]'\)/);
    assert.match(script, /addEventListener\('change'/);
    assert.match(script, /this\.form\.requestSubmit\(\)/);
});

test('mostra nello stesso modulo gli errori restituiti dal server', () => {
    assert.match(script, /mostraErroreModulo\(risultato\.message/);
    assert.match(script, /X-Requested-With': 'XMLHttpRequest'/);
});
