const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const script = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/admin-azioni.js'),
    'utf8'
);

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
