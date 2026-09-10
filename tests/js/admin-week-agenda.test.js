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

test('confirmed appointments and timed Calendar events expose drag behavior', () => {
    assert.match(template, /spostabile_locale/);
    assert.match(template, /spostabile_esterno/);
    assert.match(template, /data-week-draggable/);
    assert.match(template, /data-week-calendar-external/);
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
    assert.match(actions, /calendar-esterno\/sposta-agenda/);
});

test('weekly agenda removes summary cards and keeps appointment content readable', () => {
    const agendaStart = template.indexOf('id="admin-agenda"');
    const agendaLayout = template.indexOf('class="admin-agenda-layout', agendaStart);
    assert.ok(agendaStart >= 0);
    assert.ok(agendaLayout > agendaStart);

    const agendaHeader = template.slice(agendaStart, agendaLayout);
    assert.doesNotMatch(agendaHeader, /class="admin-command-strip"/);

    assert.match(template, /admin-week-event-title/);
    assert.match(template, /is-compact/);
    assert.match(template, /title="{{ evento\.titolo }}"/);
});
