const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const shellScript = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/admin-shell.js'),
    'utf8'
);
const patientTabsScript = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/admin-patient-tabs.js'),
    'utf8'
);
const patientTemplate = fs.readFileSync(
    path.resolve(__dirname, '../../templates/admin_paziente.html'),
    'utf8'
);
const adminLayoutTemplate = fs.readFileSync(
    path.resolve(__dirname, '../../templates/admin_layout.html'),
    'utf8'
);
const adminActionsScript = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/admin-azioni.js'),
    'utf8'
);

test('porta in vista la sezione attiva della sidebar mobile', () => {
    assert.match(shellScript, /admin-shell-nav-link\.attivo/);
    assert.match(shellScript, /scrollIntoView/);
    assert.match(shellScript, /inline: 'center'/);
});

test('la sidebar principale usa semantica di navigazione e aria-current', () => {
    assert.doesNotMatch(adminLayoutTemplate, /role="tablist"/);
    assert.doesNotMatch(adminLayoutTemplate, /role="tab"/);
    assert.doesNotMatch(adminLayoutTemplate, /aria-selected/);
    assert.match(adminLayoutTemplate, /aria-current="page"/);
    assert.match(adminActionsScript, /setAttribute\('aria-current', 'page'\)/);
    assert.match(adminActionsScript, /removeAttribute\('aria-current'\)/);
    assert.doesNotMatch(adminActionsScript, /aria-selected/);
});

test('i tab paziente aggiornano selezione e pannello visibile', () => {
    assert.match(patientTabsScript, /setAttribute\('aria-selected'/);
    assert.match(patientTabsScript, /panel\.hidden = !active/);
    assert.match(patientTabsScript, /#patient-/);
});

test('i tab paziente supportano frecce, inizio e fine', () => {
    assert.match(patientTabsScript, /ArrowLeft/);
    assert.match(patientTabsScript, /ArrowRight/);
    assert.match(patientTabsScript, /Home/);
    assert.match(patientTabsScript, /End/);
});

test('le aree paziente non implementate non espongono azioni simulate', () => {
    assert.match(patientTemplate, /Area futura/);
    assert.match(patientTemplate, /non sono ancora abilitate/);
    assert.match(patientTemplate, /non sono ancora abilitati/);
    assert.doesNotMatch(patientTemplate, /data-preview-action/);
});
