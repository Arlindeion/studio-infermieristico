const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scriptPath = path.resolve(__dirname, '../../static/js/menu-mobile.js');
const menuScript = fs.readFileSync(scriptPath, 'utf8');

class FakeClassList {
    constructor(initial = []) {
        this.values = new Set(initial);
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

    toggle(name, force) {
        const enabled = force === undefined ? !this.contains(name) : force;
        if (enabled) {
            this.add(name);
        } else {
            this.remove(name);
        }
        return enabled;
    }
}

class FakeStyle {
    constructor() {
        this.values = new Map();
    }

    setProperty(name, value) {
        this.values.set(name, value);
    }

    getPropertyValue(name) {
        return this.values.get(name) || '';
    }
}

class FakeEventTarget {
    constructor() {
        this.listeners = new Map();
    }

    addEventListener(type, listener) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(listener);
        this.listeners.set(type, listeners);
    }

    dispatch(type, properties = {}) {
        const event = {
            key: '',
            relatedTarget: null,
            shiftKey: false,
            target: this,
            defaultPrevented: false,
            propagationStopped: false,
            preventDefault() {
                this.defaultPrevented = true;
            },
            stopPropagation() {
                this.propagationStopped = true;
            },
            ...properties,
        };
        (this.listeners.get(type) || []).forEach((listener) => listener(event));
        return event;
    }
}

class FakeElement extends FakeEventTarget {
    constructor(document, options = {}) {
        super();
        this.document = document;
        this.tagName = (options.tagName || 'div').toUpperCase();
        this.attributes = new Map(Object.entries(options.attributes || {}));
        this.classList = new FakeClassList(options.classes || []);
        this.style = new FakeStyle();
        this.textContent = options.textContent || '';
        this.parentElement = null;
        this.rect = options.rect || { left: 0, width: 0 };
        this.selectors = new Map();
        this.selectorLists = new Map();
    }

    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }

    getAttribute(name) {
        return this.attributes.has(name) ? this.attributes.get(name) : null;
    }

    removeAttribute(name) {
        this.attributes.delete(name);
    }

    hasAttribute(name) {
        return this.attributes.has(name);
    }

    querySelector(selector) {
        return this.selectors.get(selector) || null;
    }

    querySelectorAll(selector) {
        return this.selectorLists.get(selector) || [];
    }

    contains(element) {
        let current = element;
        while (current) {
            if (current === this) {
                return true;
            }
            current = current.parentElement;
        }
        return false;
    }

    closest(selector) {
        let current = this;
        while (current) {
            if (selector === '[inert]' && current.hasAttribute('inert')) {
                return current;
            }
            if (selector === 'a' && current.tagName === 'A') {
                return current;
            }
            current = current.parentElement;
        }
        return null;
    }

    focus() {
        this.document.activeElement = this;
    }

    getBoundingClientRect() {
        return this.rect;
    }
}

class FakeDocument extends FakeEventTarget {
    constructor() {
        super();
        this.selectors = new Map();
        this.elements = new Set();
        this.body = this.createElement({ tagName: 'body' });
        this.activeElement = this.body;
    }

    createElement(options = {}) {
        const element = new FakeElement(this, options);
        this.elements.add(element);
        return element;
    }

    querySelector(selector) {
        return this.selectors.get(selector) || null;
    }

    contains(element) {
        return this.elements.has(element);
    }
}

class FakeWindow extends FakeEventTarget {
    constructor(media) {
        super();
        this.media = media;
        this.scrollY = 0;
    }

    matchMedia() {
        return this.media;
    }
}

function connect(parent, ...children) {
    children.forEach((child) => {
        child.parentElement = parent;
    });
}

function bootHeader() {
    const document = new FakeDocument();
    const media = new FakeEventTarget();
    media.matches = true;
    const window = new FakeWindow(media);
    const frameQueue = new Map();
    let nextFrameId = 1;

    const requestAnimationFrame = (callback) => {
        const id = nextFrameId;
        nextFrameId += 1;
        frameQueue.set(id, callback);
        return id;
    };
    const cancelAnimationFrame = (id) => frameQueue.delete(id);
    const flushFrames = () => {
        while (frameQueue.size) {
            const callbacks = Array.from(frameQueue.values());
            frameQueue.clear();
            callbacks.forEach((callback) => callback());
        }
    };

    const header = document.createElement();
    const desktopNav = document.createElement({ rect: { left: 100, width: 700 } });
    const currentItem = document.createElement({ rect: { left: 120, width: 50 } });
    const secondItem = document.createElement({ rect: { left: 220, width: 130 } });
    const dropdown = document.createElement();
    const dropdownToggle = document.createElement({
        tagName: 'button',
        attributes: { 'aria-expanded': 'false' },
    });
    const dropdownPanel = document.createElement({
        attributes: { 'aria-hidden': 'true', inert: '' },
    });
    const menuToggle = document.createElement({
        tagName: 'button',
        attributes: { 'aria-expanded': 'false', 'aria-label': 'Apri il menu' },
    });
    const menuText = document.createElement({ textContent: 'Menu' });
    const mobileNav = document.createElement({
        attributes: { 'aria-hidden': 'true', inert: '' },
    });
    const firstPillar = document.createElement({ tagName: 'a' });
    const secondPillar = document.createElement({ tagName: 'a' });
    const closeButton = document.createElement({ tagName: 'button' });
    const mobileCoursesToggle = document.createElement({
        tagName: 'button',
        attributes: { 'aria-expanded': 'false' },
    });
    const mobileCoursesList = document.createElement({
        attributes: { 'aria-hidden': 'true', inert: '' },
    });
    const nestedCourseLink = document.createElement({ tagName: 'a' });
    const lastLink = document.createElement({ tagName: 'a' });

    connect(dropdown, dropdownToggle, dropdownPanel);
    connect(menuToggle, menuText);
    connect(mobileNav, firstPillar, secondPillar, closeButton, mobileCoursesToggle, mobileCoursesList, lastLink);
    connect(mobileCoursesList, nestedCourseLink);
    connect(desktopNav, currentItem, secondItem, dropdown);

    desktopNav.selectorLists.set('[data-nav-item]', [currentItem, secondItem]);
    desktopNav.selectors.set('[data-nav-current]', currentItem);
    menuToggle.selectors.set('.menu-toggle__text', menuText);
    mobileNav.selectors.set('.mobile-nav__pillar', firstPillar);
    mobileNav.selectors.set('[data-menu-close]', closeButton);
    mobileNav.selectorLists.set(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        [firstPillar, secondPillar, nestedCourseLink, lastLink],
    );

    document.selectors.set('[data-site-header]', header);
    document.selectors.set('[data-desktop-nav]', desktopNav);
    document.selectors.set('[data-nav-dropdown]', dropdown);
    document.selectors.set('[data-nav-dropdown-toggle]', dropdownToggle);
    document.selectors.set('[data-nav-dropdown-panel]', dropdownPanel);
    document.selectors.set('[data-menu-toggle]', menuToggle);
    document.selectors.set('[data-mobile-nav]', mobileNav);
    document.selectors.set('[data-mobile-courses-toggle]', mobileCoursesToggle);
    document.selectors.set('[data-mobile-courses-list]', mobileCoursesList);

    const context = vm.createContext({
        cancelAnimationFrame,
        document,
        requestAnimationFrame,
        window,
    });
    vm.runInContext(menuScript, context, { filename: scriptPath });
    document.dispatch('DOMContentLoaded');
    flushFrames();

    return {
        document,
        window,
        flushFrames,
        elements: {
            currentItem,
            desktopNav,
            dropdown,
            dropdownPanel,
            dropdownToggle,
            firstPillar,
            header,
            lastLink,
            menuToggle,
            mobileCoursesList,
            mobileCoursesToggle,
            mobileNav,
            secondItem,
        },
    };
}

test('apre e chiude il dropdown corsi aggiornando stato e focus', () => {
    const { document, elements } = bootHeader();
    const { dropdown, dropdownPanel, dropdownToggle } = elements;

    dropdownToggle.dispatch('click');
    assert.equal(dropdownToggle.getAttribute('aria-expanded'), 'true');
    assert.equal(dropdownPanel.getAttribute('aria-hidden'), 'false');
    assert.equal(dropdownPanel.hasAttribute('inert'), false);
    assert.equal(dropdown.classList.contains('is-open'), true);

    document.dispatch('keydown', { key: 'Escape' });
    assert.equal(dropdownToggle.getAttribute('aria-expanded'), 'false');
    assert.equal(dropdownPanel.getAttribute('aria-hidden'), 'true');
    assert.equal(dropdownPanel.hasAttribute('inert'), true);
    assert.equal(document.activeElement, dropdownToggle);
});

test('intrappola il focus nel menu mobile e lo ripristina alla chiusura', () => {
    const { document, flushFrames, elements } = bootHeader();
    const { firstPillar, lastLink, menuToggle, mobileNav } = elements;

    menuToggle.focus();
    menuToggle.dispatch('click');
    flushFrames();

    assert.equal(menuToggle.getAttribute('aria-expanded'), 'true');
    assert.equal(mobileNav.getAttribute('aria-hidden'), 'false');
    assert.equal(mobileNav.hasAttribute('inert'), false);
    assert.equal(document.body.classList.contains('menu-open'), true);
    assert.equal(document.activeElement, firstPillar);

    lastLink.focus();
    const forwardTab = document.dispatch('keydown', { key: 'Tab' });
    assert.equal(forwardTab.defaultPrevented, true);
    assert.equal(document.activeElement, firstPillar);

    const backwardTab = document.dispatch('keydown', { key: 'Tab', shiftKey: true });
    assert.equal(backwardTab.defaultPrevented, true);
    assert.equal(document.activeElement, lastLink);

    document.dispatch('keydown', { key: 'Escape' });
    assert.equal(menuToggle.getAttribute('aria-expanded'), 'false');
    assert.equal(mobileNav.hasAttribute('inert'), true);
    assert.equal(document.body.classList.contains('menu-open'), false);
    assert.equal(document.activeElement, menuToggle);
});

test('apre l’elenco corsi mobile rendendo i link raggiungibili', () => {
    const { elements } = bootHeader();
    const { mobileCoursesList, mobileCoursesToggle } = elements;

    mobileCoursesToggle.dispatch('click');
    assert.equal(mobileCoursesToggle.getAttribute('aria-expanded'), 'true');
    assert.equal(mobileCoursesList.getAttribute('aria-hidden'), 'false');
    assert.equal(mobileCoursesList.hasAttribute('inert'), false);
    assert.equal(mobileCoursesList.classList.contains('is-open'), true);
});

test('sposta il filo sull’elemento esplorato e torna a quello corrente', () => {
    const { elements } = bootHeader();
    const { desktopNav, secondItem } = elements;

    assert.equal(desktopNav.style.getPropertyValue('--thread-x'), '20px');
    assert.equal(desktopNav.style.getPropertyValue('--thread-width'), '50px');

    secondItem.dispatch('pointerenter');
    assert.equal(desktopNav.style.getPropertyValue('--thread-x'), '120px');
    assert.equal(desktopNav.style.getPropertyValue('--thread-width'), '130px');

    desktopNav.dispatch('pointerleave');
    assert.equal(desktopNav.style.getPropertyValue('--thread-x'), '20px');
    assert.equal(desktopNav.style.getPropertyValue('--thread-width'), '50px');
});

test('aggiorna lo stato compatto dell’header durante lo scroll', () => {
    const { window, flushFrames, elements } = bootHeader();
    const { header } = elements;

    window.scrollY = 24;
    window.dispatch('scroll');
    flushFrames();
    assert.equal(header.classList.contains('is-scrolled'), true);

    window.scrollY = 0;
    window.dispatch('scroll');
    flushFrames();
    assert.equal(header.classList.contains('is-scrolled'), false);
});
