const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scriptPath = path.resolve(__dirname, '../../static/js/page-transitions.js');
const transitionScript = fs.readFileSync(scriptPath, 'utf8');

class FakeClassList {
    constructor() {
        this.values = new Set();
    }

    add(...names) {
        names.forEach((name) => this.values.add(name));
    }

    remove(...names) {
        names.forEach((name) => this.values.delete(name));
    }

    contains(name) {
        return this.values.has(name);
    }
}

function bootPage({ url, reducedMotion = false, historyState = null, storedValues = {} }) {
    const documentListeners = new Map();
    const windowListeners = new Map();
    const storage = new Map(Object.entries(storedValues));
    const assignedUrls = [];
    const appendedElements = [];
    const previewTargets = new Map();
    const timers = [];
    const root = {
        attributes: new Map(),
        classList: new FakeClassList(),
        style: {
            values: new Map(),
            setProperty(name, value) {
                this.values.set(name, value);
            },
            removeProperty(name) {
                this.values.delete(name);
            },
        },
        setAttribute(name, value) {
            this.attributes.set(name, value);
        },
        removeAttribute(name) {
            this.attributes.delete(name);
        },
    };
    const currentUrl = new URL(url);
    const location = {
        href: currentUrl.href,
        origin: currentUrl.origin,
        pathname: currentUrl.pathname,
        search: currentUrl.search,
        assign(destination) {
            assignedUrls.push(destination);
        },
    };
    const history = {
        state: historyState,
        replaceState(state) {
            this.state = state;
        },
    };
    const document = {
        documentElement: root,
        readyState: 'complete',
        body: {
            append(element) {
                appendedElements.push(element);
            },
        },
        addEventListener(type, listener) {
            documentListeners.set(type, listener);
        },
        createElement(tagName) {
            const listeners = new Map();
            const element = {
                attributes: new Map(),
                children: [],
                classList: new FakeClassList(),
                className: '',
                listeners,
                removed: false,
                append(child) {
                    this.children.push(child);
                },
                addEventListener(type, listener) {
                    listeners.set(type, listener);
                },
                setAttribute(name, value) {
                    this.attributes.set(name, value);
                },
                remove() {
                    this.removed = true;
                },
            };
            if (tagName === 'iframe') {
                const previewHead = { append() {} };
                element.contentDocument = {
                    URL: 'about:blank',
                    body: { classList: new FakeClassList(), scrollTop: 0 },
                    documentElement: { classList: new FakeClassList(), scrollTop: 0 },
                    head: previewHead,
                    createElement() {
                        return { textContent: '' };
                    },
                    getElementById(id) {
                        return previewTargets.get(id) || null;
                    },
                    querySelector() {
                        return null;
                    },
                };
                Object.defineProperty(element, 'src', {
                    get() {
                        return this.contentDocument.URL;
                    },
                    set(value) {
                        this.contentDocument.URL = value;
                    },
                });
            }
            return element;
        },
        querySelector(selector) {
            if (selector === '[data-site-header]') {
                return { getBoundingClientRect: () => ({ bottom: 88 }) };
            }
            return null;
        },
    };
    const window = {
        document,
        history,
        location,
        sessionStorage: {
            getItem(key) {
                return storage.has(key) ? storage.get(key) : null;
            },
            setItem(key, value) {
                storage.set(key, String(value));
            },
            removeItem(key) {
                storage.delete(key);
            },
        },
        matchMedia() {
            return { matches: reducedMotion };
        },
        requestAnimationFrame(callback) {
            callback();
            return 1;
        },
        setTimeout(callback, duration) {
            const timer = { callback, duration, cleared: false };
            timers.push(timer);
            return timers.length - 1;
        },
        clearTimeout(timerIndex) {
            if (timers[timerIndex]) timers[timerIndex].cleared = true;
        },
        addEventListener(type, listener) {
            windowListeners.set(type, listener);
        },
    };

    vm.runInNewContext(transitionScript, {
        Date,
        JSON,
        Number,
        URL,
        document,
        window,
    });

    const click = (href, anchorOptions = {}) => {
        const anchor = {
            dataset: {},
            href,
            target: '',
            hasAttribute() {
                return false;
            },
            ...anchorOptions,
        };
        const event = {
            altKey: false,
            button: 0,
            ctrlKey: false,
            defaultPrevented: false,
            metaKey: false,
            shiftKey: false,
            target: { closest: () => anchor },
            preventDefault() {
                this.defaultPrevented = true;
            },
        };
        documentListeners.get('click')(event);
        return event;
    };

    return {
        appendedElements,
        assignedUrls,
        click,
        history,
        root,
        storage,
        timers,
        previewTargets,
        windowListeners,
    };
}

test('la destinazione pronta copre progressivamente la pagina corrente da destra', () => {
    const page = bootPage({ url: 'http://127.0.0.1:5000/' });
    const event = page.click('http://127.0.0.1:5000/iscrizione-corsi');
    const stage = page.appendedElements[0];
    const frame = stage.children[0];

    assert.equal(event.defaultPrevented, true);
    assert.match(stage.className, /page-transition-preview--forward/);
    assert.deepEqual(page.assignedUrls, []);

    frame.listeners.get('load')();
    assert.equal(stage.classList.contains('is-running'), true);
    assert.equal(page.root.classList.contains('page-transition-previewing'), true);
    page.timers.find(({ duration }) => duration === 640).callback();

    assert.deepEqual(page.assignedUrls, ['http://127.0.0.1:5000/iscrizione-corsi']);
    assert.equal(JSON.parse(page.storage.get('sc-page-transition-previewed')).url, 'http://127.0.0.1:5000/iscrizione-corsi');
    assert.equal(page.storage.has('sc-page-transition-pending'), false);
});

test('la homepage pronta copre progressivamente la pagina corrente da sinistra', () => {
    const page = bootPage({ url: 'http://127.0.0.1:5000/iscrizione-corsi' });
    page.click('http://127.0.0.1:5000/');
    const stage = page.appendedElements[0];
    const frame = stage.children[0];

    assert.match(stage.className, /page-transition-preview--backward/);
    frame.listeners.get('load')();
    page.timers.find(({ duration }) => duration === 640).callback();
    assert.deepEqual(page.assignedUrls, ['http://127.0.0.1:5000/']);
});

test('l\u2019anteprima apre direttamente la sezione indicata dal link', () => {
    const page = bootPage({ url: 'http://127.0.0.1:5000/' });
    let scrollOptions = null;
    page.previewTargets.set('formule', {
        scrollIntoView(options) {
            scrollOptions = options;
        },
    });

    page.click('http://127.0.0.1:5000/consulenze-online#formule');
    const frame = page.appendedElements[0].children[0];
    frame.listeners.get('load')();

    assert.equal(scrollOptions?.block, 'start');
});

test('se la preparazione è lenta apre comunque il link con entrata di riserva', () => {
    const page = bootPage({ url: 'http://127.0.0.1:5000/' });
    page.click('http://127.0.0.1:5000/consulenze-online');

    page.timers.find(({ duration }) => duration === 1800).callback();

    assert.deepEqual(page.assignedUrls, ['http://127.0.0.1:5000/consulenze-online']);
    assert.equal(JSON.parse(page.storage.get('sc-page-transition-pending')).direction, 'forward');
});

test('non ripete l’entrata quando il documento reale sostituisce l’anteprima', () => {
    const destination = 'http://127.0.0.1:5000/iscrizione-corsi';
    const page = bootPage({
        url: destination,
        historyState: { __scPageTransitionIndex: 2 },
        storedValues: {
            'sc-page-transition-active-index': '1',
            'sc-page-transition-previewed': JSON.stringify({
                createdAt: Date.now(),
                url: destination,
            }),
        },
    });

    assert.equal(page.root.classList.contains('page-transition-arrived'), true);
    assert.equal(page.root.classList.contains('page-transition-active'), false);
    assert.equal(page.root.classList.contains('page-transition-running'), false);
});

test('riconosce una pagina precedente ripristinata dalla cronologia', () => {
    const page = bootPage({
        url: 'http://127.0.0.1:5000/',
        historyState: { __scPageTransitionIndex: 1 },
        storedValues: { 'sc-page-transition-active-index': '2' },
    });

    assert.equal(page.root.classList.contains('page-transition-enter-backward'), true);
    assert.equal(page.root.classList.contains('page-transition-running'), true);
});

test('lascia immediata la navigazione con movimento ridotto o link esterno', () => {
    const reducedPage = bootPage({ url: 'http://127.0.0.1:5000/', reducedMotion: true });
    const reducedEvent = reducedPage.click('http://127.0.0.1:5000/iscrizione-corsi');
    const standardPage = bootPage({ url: 'http://127.0.0.1:5000/' });
    const externalEvent = standardPage.click('https://example.com/');

    assert.equal(reducedEvent.defaultPrevented, false);
    assert.equal(externalEvent.defaultPrevented, false);
});
