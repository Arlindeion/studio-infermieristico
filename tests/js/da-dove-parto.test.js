const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const script = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/da-dove-parto.js'),
    'utf8'
);

test('il quiz orienta localmente senza inviare o persistere risposte', () => {
    assert.match(script, /const percorsi =/);
    assert.match(script, /\/aziende-e-gruppi/);
    assert.match(script, /\/prestazioni-infermieristiche/);
    assert.match(script, /\/consulenze-online/);
    assert.doesNotMatch(script, /fetch\(|XMLHttpRequest|localStorage|sessionStorage|document\.cookie/);
});

test('il quiz mantiene navigazione indietro e reset', () => {
    assert.match(script, /data-quiz-back/);
    assert.match(script, /data-quiz-reset/);
    assert.match(script, /showStep\('start'\)/);
    assert.match(script, /\.focus\(/);
});
