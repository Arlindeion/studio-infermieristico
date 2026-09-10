const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const template = fs.readFileSync(path.resolve(__dirname, '../../templates/admin.html'), 'utf8');
const actions = fs.readFileSync(path.resolve(__dirname, '../../static/js/admin-azioni.js'), 'utf8');

test('agenda admin opens on the weekly grid contract', () => {
    assert.match(template, /data-admin-week-grid/);
    assert.match(template, /data-week-day=/);
    assert.match(template, /data-week-event/);
});

test('only confirmed appointment cards expose drag behavior', () => {
    assert.match(template, /evento\.tipo == 'Appuntamento'/);
    assert.match(template, /evento\.stato == 'Confermato'/);
    assert.match(template, /draggable="true" data-week-appointment/);
});

test('dragging uses a three-choice confirmation dialog', () => {
    assert.match(template, />Annulla</);
    assert.match(template, />Conferma e manda mail al paziente</);
    assert.match(template, />Conferma senza mail</);
    assert.match(actions, /dragstart/);
    assert.match(actions, /dragover/);
    assert.match(actions, /drop/);
});

test('drag confirmation posts the old and new slot plus explicit mail choice', () => {
    assert.match(actions, /data_originale/);
    assert.match(actions, /ora_originale/);
    assert.match(actions, /invia_email/);
    assert.match(actions, /sposta-agenda/);
});
