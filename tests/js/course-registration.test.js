const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const script = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/course-registration.js'),
    'utf8'
);

test('aggiorna il luogo fisso quando cambia la data del corso', () => {
    assert.match(script, /\[data-course-date-select\]/);
    assert.match(script, /\[data-course-location-output\]/);
    assert.match(script, /selectedOptions\[0\]/);
    assert.match(script, /dataset\.courseLocation/);
    assert.match(script, /dateSelect\.addEventListener\('change', updateCourseLocation\)/);
});

test('non genera errori nelle pagine prive dei campi corso', () => {
    assert.match(script, /if \(!dateSelect \|\| !locationOutput\) return;/);
});
