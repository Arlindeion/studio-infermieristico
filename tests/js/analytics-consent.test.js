const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const consentScript = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/analytics-consent.js'),
    'utf8'
);
const conversionScript = fs.readFileSync(
    path.resolve(__dirname, '../../static/js/conversion-tracking.js'),
    'utf8'
);

class FakeEventTarget {
    constructor() {
        this.listeners = new Map();
    }

    addEventListener(type, listener) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(listener);
        this.listeners.set(type, listeners);
    }

    dispatch(type, event = {}) {
        (this.listeners.get(type) || []).forEach((listener) => listener(event));
    }
}

class FakeElement extends FakeEventTarget {
    constructor(document, tagName = 'div') {
        super();
        this.document = document;
        this.tagName = tagName.toUpperCase();
        this.attributes = new Map();
        this.dataset = {};
        this.className = '';
        this.content = '';
        this.innerHTML = '';
        this.async = false;
        this.src = '';
    }

    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }

    remove() {
        if (this.document.banner === this) {
            this.document.banner = null;
        }
    }
}

class FakeDocument extends FakeEventTarget {
    constructor(options = {}) {
        super();
        this.meta = new FakeElement(this, 'meta');
        this.meta.content = options.measurementId || 'G-TEST123';
        this.preferences = new FakeElement(this, 'button');
        this.banner = null;
        this.scripts = [];
        this.cookieValue = options.cookies || '';
        this.cookieWrites = [];
        this.head = {
            appendChild: (element) => {
                this.scripts.push(element);
            }
        };
        this.body = {
            appendChild: (element) => {
                if (element.className === 'cookie-banner') {
                    this.banner = element;
                }
            }
        };
    }

    querySelector(selector) {
        if (selector === 'meta[name="google-analytics-id"]') {
            return this.meta;
        }
        if (selector === '.cookie-banner') {
            return this.banner;
        }
        return null;
    }

    getElementById(id) {
        return id === 'cookie-preferences' ? this.preferences : null;
    }

    createElement(tagName) {
        return new FakeElement(this, tagName);
    }

    get cookie() {
        return this.cookieValue;
    }

    set cookie(value) {
        this.cookieWrites.push(value);
    }
}

function createConsentEnvironment(options = {}) {
    const document = new FakeDocument(options);
    const values = new Map();
    if (options.savedChoice) {
        values.set('sc_analytics_consent', options.savedChoice);
    }
    const localStorage = {
        getItem(key) {
            return values.has(key) ? values.get(key) : null;
        },
        setItem(key, value) {
            values.set(key, String(value));
        }
    };
    const window = {};
    const context = {
        Date,
        document,
        encodeURIComponent,
        localStorage,
        window
    };
    window.window = window;
    window.document = document;
    window.localStorage = localStorage;
    vm.runInNewContext(consentScript, context);
    document.dispatch('DOMContentLoaded');
    return { document, localStorage, values, window };
}

function clickCookieChoice(environment, choice) {
    const choiceButton = {
        dataset: { cookieChoice: choice }
    };
    environment.document.banner.dispatch('click', {
        target: {
            closest(selector) {
                return selector === '[data-cookie-choice]' ? choiceButton : null;
            }
        }
    });
}

function gtagCalls(window) {
    return (window.dataLayer || []).map((entry) => Array.from(entry));
}

test('non carica Google Analytics prima di una scelta', () => {
    const environment = createConsentEnvironment();

    assert.ok(environment.document.banner);
    assert.equal(environment.document.scripts.length, 0);
    assert.equal(environment.window.gtag, undefined);
});

test('accettare carica GA e aggiorna il consenso prima della configurazione', () => {
    const environment = createConsentEnvironment();

    clickCookieChoice(environment, 'accepted');

    assert.equal(environment.values.get('sc_analytics_consent'), 'accepted');
    assert.equal(environment.document.banner, null);
    assert.equal(environment.document.scripts.length, 1);
    assert.equal(
        environment.document.scripts[0].src,
        'https://www.googletagmanager.com/gtag/js?id=G-TEST123'
    );
    const calls = gtagCalls(environment.window);
    assert.deepEqual(calls[0].slice(0, 2), ['consent', 'default']);
    assert.equal(calls[0][2].analytics_storage, 'denied');
    assert.deepEqual(calls[1].slice(0, 2), ['consent', 'update']);
    assert.equal(calls[1][2].analytics_storage, 'granted');
    assert.deepEqual(calls[3].slice(0, 2), ['config', 'G-TEST123']);
});

test('una scelta rifiutata persistente non carica GA né riapre il banner', () => {
    const environment = createConsentEnvironment({ savedChoice: 'rejected' });

    assert.equal(environment.document.banner, null);
    assert.equal(environment.document.scripts.length, 0);
    assert.equal(environment.window.gtag, undefined);
});

test('una scelta non riconosciuta riapre il banner senza caricare GA', () => {
    const environment = createConsentEnvironment({ savedChoice: 'valore-obsoleto' });

    assert.ok(environment.document.banner);
    assert.equal(environment.document.scripts.length, 0);
});

test('revocare aggiorna il consenso e rimuove i cookie Analytics', () => {
    const environment = createConsentEnvironment({
        savedChoice: 'accepted',
        cookies: '_ga=abc; _ga_TEST=def; _gid=ghi; session=tecnica'
    });

    environment.document.preferences.dispatch('click');
    assert.ok(environment.document.banner);
    clickCookieChoice(environment, 'rejected');

    assert.equal(environment.values.get('sc_analytics_consent'), 'rejected');
    const calls = gtagCalls(environment.window);
    const lastConsentCall = calls.filter(
        (call) => call[0] === 'consent' && call[1] === 'update'
    ).at(-1);
    assert.equal(lastConsentCall[2].analytics_storage, 'denied');
    assert.ok(environment.document.cookieWrites.some((value) => value.startsWith('_ga=')));
    assert.ok(environment.document.cookieWrites.some((value) => value.startsWith('_ga_TEST=')));
    assert.ok(environment.document.cookieWrites.some((value) => value.startsWith('_gid=')));
    assert.ok(!environment.document.cookieWrites.some((value) => value.startsWith('session=')));
});

function runConversionTracking(savedChoice) {
    const document = new FakeEventTarget();
    const calls = [];
    const window = {
        location: { pathname: '/consulenze-online' },
        gtag(...args) {
            calls.push(args);
        }
    };
    const localStorage = {
        getItem() {
            return savedChoice;
        }
    };
    vm.runInNewContext(conversionScript, {
        document,
        localStorage,
        window
    });
    document.dispatch('click', {
        target: {
            closest(selector) {
                if (selector !== '[data-conversion]') {
                    return null;
                }
                return {
                    dataset: { conversion: 'sleep_booking' },
                    href: 'https://example.test/prenota-call-sonno'
                };
            }
        }
    });
    return calls;
}

test('il tracciamento conversioni parte soltanto con consenso accettato', () => {
    assert.equal(runConversionTracking(null).length, 0);
    assert.equal(runConversionTracking('rejected').length, 0);

    const acceptedCalls = runConversionTracking('accepted');
    assert.equal(acceptedCalls.length, 1);
    assert.equal(acceptedCalls[0][0], 'event');
    assert.equal(acceptedCalls[0][1], 'conversion_click');
    assert.equal(acceptedCalls[0][2].conversion_name, 'sleep_booking');
});
