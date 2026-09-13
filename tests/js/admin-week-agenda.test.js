const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const template = fs.readFileSync(path.resolve(__dirname, '../../templates/admin.html'), 'utf8');
const actions = fs.readFileSync(path.resolve(__dirname, '../../static/js/admin-azioni.js'), 'utf8');
const adminCss = fs.readFileSync(path.resolve(__dirname, '../../static/css/admin.css'), 'utf8');

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


test('weekly toolbar is compact, keeps the period controls and orders the views', () => {
    const agendaStart = template.indexOf('id="admin-agenda"');
    const agendaLayout = template.indexOf('class="admin-agenda-layout', agendaStart);
    const header = template.slice(agendaStart, agendaLayout);

    const settimana = header.indexOf('>Settimana</a>');
    const mese = header.indexOf('>Mese</a>');
    const giorno = header.indexOf('>Giorno</a>');
    assert.ok(settimana >= 0 && mese > settimana && giorno > mese);
    assert.match(header, /admin-period-label/);
    assert.match(header, /admin-calendar-today/);
    assert.match(header, /admin-month-picker/);
    assert.match(template, /data-week-search-toggle/);
    assert.match(template, /data-week-search-popover/);
});

test('weekly appointment hover opens after one second with edit, optional detail and delete actions', () => {
    assert.match(template, /admin-week-detail-template/);
    assert.match(template, /data-week-detail-edit/);
    assert.match(template, /data-week-detail-open/);
    assert.match(template, /data-week-detail-delete/);
    assert.match(actions, /HOVER_SETTIMANA_MS = 1000/);
    assert.match(actions, /window\.confirm/);
    assert.match(actions, /modifica-agenda/);
    assert.match(actions, /elimina-agenda/);
});

test('weekly details are available by keyboard and touch with accessible targets', () => {
    assert.match(template, /tabindex="0"/);
    assert.match(template, /aria-haspopup="dialog"/);
    assert.match(actions, /event\.key !== 'Enter'/);
    assert.match(actions, /evento\.addEventListener\('click'/);
    assert.match(actions, /aria-expanded/);
});

test('quick editing sends the original snapshot to reject stale pages', () => {
    assert.match(template, /name="original_date"/);
    assert.match(template, /name="original_time"/);
    assert.match(template, /name="original_duration"/);
    assert.match(actions, /elements\.original_date\.value/);
    assert.match(actions, /elements\.original_note\.value/);
});

test('quick editing hides fields that do not belong to the selected event type', () => {
    assert.match(adminCss, /\.admin-week-edit-form \[hidden\]\s*\{\s*display:\s*none;/);
    assert.match(actions, /localFields\.hidden = esterno;/);
    assert.match(actions, /externalField\.hidden = !esterno;/);
});
