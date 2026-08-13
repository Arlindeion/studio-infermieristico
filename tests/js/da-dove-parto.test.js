const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const stylesheet = fs.readFileSync(
    path.resolve(__dirname, '../../static/css/orientamento.css'),
    'utf8'
);
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
    assert.match(script, /showStep\('start', 'backward'\)/);
    assert.match(script, /\.focus\(/);
});

test('i passaggi usano lo stesso scorrimento laterale del sito', () => {
    assert.match(script, /transitionDuration = 620/);
    assert.match(script, /is-entering-\$\{direction\}/);
    assert.match(script, /transitionTo\(resultPanel, 'forward'/);
    assert.match(stylesheet, /orientation-panel-in-forward 620ms cubic-bezier\(0\.65, 0, 0\.35, 1\)/);
    assert.match(stylesheet, /orientation-panel-in-backward 620ms cubic-bezier\(0\.65, 0, 0\.35, 1\)/);
    assert.match(stylesheet, /background: var\(--rosso-cuore\)/);
});

test('il quiz rispetta la preferenza movimento ridotto', () => {
    assert.match(script, /prefers-reduced-motion: reduce/);
    assert.match(script, /reducedMotion\.matches/);
    assert.match(stylesheet, /prefers-reduced-motion: reduce/);
});
