(() => {
    'use strict';

    const root = document.documentElement;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const transitionClasses = [
        'page-transition-active',
        'page-transition-running',
        'page-transition-enter-forward',
        'page-transition-enter-backward',
        'page-transition-previewing',
    ];
    const stateKey = '__scPageTransitionIndex';
    const activeIndexKey = 'sc-page-transition-active-index';
    const counterKey = 'sc-page-transition-counter';
    const pendingKey = 'sc-page-transition-pending';
    const previewedKey = 'sc-page-transition-previewed';
    const entryDuration = 500;
    const previewDuration = 640;
    const previewLoadTimeout = 1800;
    let navigationStarted = false;
    let previewStage = null;

    const safeStorage = {
        get(key) {
            try {
                return window.sessionStorage.getItem(key);
            } catch (_error) {
                return null;
            }
        },
        set(key, value) {
            try {
                window.sessionStorage.setItem(key, value);
            } catch (_error) {
                // La navigazione resta disponibile anche con lo storage disabilitato.
            }
        },
        remove(key) {
            try {
                window.sessionStorage.removeItem(key);
            } catch (_error) {
                // Nessuna pulizia necessaria quando lo storage non è disponibile.
            }
        },
    };

    const numericStorageValue = (key) => {
        const value = Number.parseInt(safeStorage.get(key) || '', 10);
        return Number.isFinite(value) ? value : null;
    };

    const nextHistoryIndex = () => {
        const counter = numericStorageValue(counterKey) || 0;
        const activeIndex = numericStorageValue(activeIndexKey) || 0;
        const nextIndex = Math.max(counter, activeIndex) + 1;
        safeStorage.set(counterKey, String(nextIndex));
        return nextIndex;
    };

    const existingIndex = window.history.state?.[stateKey];
    const currentIndex = Number.isFinite(existingIndex) ? existingIndex : nextHistoryIndex();
    if (!Number.isFinite(existingIndex)) {
        window.history.replaceState({
            ...(window.history.state || {}),
            [stateKey]: currentIndex,
        }, '', window.location.href);
    }

    const clearTransition = () => {
        root.classList.remove(...transitionClasses);
        root.style.removeProperty('--page-transition-header-height');
        root.removeAttribute('aria-busy');
        if (previewStage) {
            previewStage.remove();
            previewStage = null;
        }
    };

    const readStoredNavigation = (key) => {
        const serialized = safeStorage.get(key);
        safeStorage.remove(key);
        if (!serialized) return null;

        try {
            const navigation = JSON.parse(serialized);
            const isRecent = Date.now() - navigation.createdAt < 5000;
            return isRecent && navigation.url === window.location.href
                ? navigation
                : null;
        } catch (_error) {
            return null;
        }
    };

    const inferredDirection = () => {
        const previousIndex = numericStorageValue(activeIndexKey);
        if (previousIndex === null || previousIndex === currentIndex) return null;
        return currentIndex < previousIndex ? 'backward' : 'forward';
    };

    const runEntry = (direction) => {
        clearTransition();
        if (!direction || reducedMotion.matches || window.location.pathname.startsWith('/admin')) {
            safeStorage.set(activeIndexKey, String(currentIndex));
            return;
        }

        root.classList.add('page-transition-active', `page-transition-enter-${direction}`);
        root.setAttribute('aria-busy', 'true');
        safeStorage.set(activeIndexKey, String(currentIndex));

        const start = () => {
            window.requestAnimationFrame(() => {
                root.classList.add('page-transition-running');
                window.setTimeout(clearTransition, entryDuration);
            });
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', start, { once: true });
        } else {
            start();
        }
    };

    const previewedNavigation = readStoredNavigation(previewedKey);
    if (previewedNavigation) {
        safeStorage.remove(pendingKey);
        root.classList.add('page-transition-arrived');
        window.addEventListener('load', () => {
            window.setTimeout(() => root.classList.remove('page-transition-arrived'), 800);
        }, { once: true });
    }
    const pendingNavigation = previewedNavigation ? null : readStoredNavigation(pendingKey);
    const entryDirection = previewedNavigation
        ? null
        : (pendingNavigation?.direction || inferredDirection());
    runEntry(entryDirection);

    window.addEventListener('pageshow', (event) => {
        if (!event.persisted) return;
        navigationStarted = false;
        runEntry(inferredDirection());
    });

    const shouldTransition = (event, anchor, destination) => {
        if (navigationStarted || reducedMotion.matches || event.defaultPrevented) return false;
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
        if (anchor.hasAttribute('download') || anchor.dataset.noPageTransition !== undefined) return false;
        if (anchor.target && anchor.target !== '_self') return false;
        if (!['http:', 'https:'].includes(destination.protocol)) return false;
        if (destination.origin !== window.location.origin) return false;
        if (window.location.pathname.startsWith('/admin') || destination.pathname.startsWith('/admin')) return false;

        const sameDocument = destination.pathname === window.location.pathname
            && destination.search === window.location.search;
        if (sameDocument && (destination.hash || destination.href === window.location.href)) return false;
        return true;
    };

    const rememberPendingEntry = (destination, direction) => {
        safeStorage.set(pendingKey, JSON.stringify({
            createdAt: Date.now(),
            direction,
            url: destination.href,
        }));
    };

    const navigateWithFallback = (destination, direction) => {
        clearTransition();
        rememberPendingEntry(destination, direction);
        window.location.assign(destination.href);
    };

    const scrollPreviewToDestination = (previewDocument, destination) => {
        let targetId = '';
        try {
            targetId = decodeURIComponent(destination.hash.slice(1));
        } catch (_error) {
            targetId = destination.hash.slice(1);
        }

        const target = targetId ? previewDocument.getElementById(targetId) : null;
        if (target) {
            target.scrollIntoView({ block: 'start' });
            return;
        }

        previewDocument.documentElement.scrollTop = 0;
        previewDocument.body.scrollTop = 0;
    };

    const preparePreviewDocument = (frame, destination) => {
        const previewDocument = frame.contentDocument;
        if (!previewDocument?.body || previewDocument.URL === 'about:blank') return false;

        const previewStyles = previewDocument.createElement('style');
        previewStyles.textContent = `
            .site-header {
                pointer-events: none !important;
                visibility: hidden !important;
            }
            .mobile-nav,
            .skip-link,
            .sticky-prenota,
            .cookie-banner,
            .home-scene-nav,
            .home-object-handoff {
                display: none !important;
            }
            html {
                overflow: hidden !important;
                scroll-behavior: auto !important;
            }
        `;
        previewDocument.head.append(previewStyles);
        scrollPreviewToDestination(previewDocument, destination);

        if (previewDocument.body.classList.contains('page-homepage')) {
            const parallaxStage = previewDocument.querySelector('[data-home-parallax]');
            const parallaxBackground = previewDocument.querySelector('.home-hero-photo-background');
            if (parallaxBackground?.complete && parallaxBackground.naturalWidth > 0) {
                parallaxStage?.classList.add('is-parallax-ready');
            }

            const desktopSnap = window.matchMedia('(min-width: 1024px) and (min-height: 640px)').matches;
            if (desktopSnap && !reducedMotion.matches) {
                previewDocument.documentElement.classList.add(
                    'home-scroll-snap',
                    'home-depth-ready',
                    'home-scroll-story-ready',
                );
                previewDocument.body.classList.add('home-motion-scene-intro');
                const firstScene = previewDocument.querySelector('[data-home-scene]');
                firstScene?.classList.add('is-scene-current', 'is-scene-seen');
            }
        }
        return true;
    };

    const previewAssetsReady = (frame) => {
        const previewDocument = frame.contentDocument;
        if (!previewDocument?.body || previewDocument.URL === 'about:blank') return false;
        if (previewDocument.readyState === 'loading') return false;
        if (previewDocument.fonts?.status === 'loading') return false;

        const viewportHeight = frame.contentWindow?.innerHeight || window.innerHeight;
        return Array.from(previewDocument.images || []).every((image) => {
            const bounds = image.getBoundingClientRect();
            const outsideFirstViewport = bounds.top >= viewportHeight || bounds.bottom <= 0;
            return outsideFirstViewport || (image.complete && image.naturalWidth > 0);
        });
    };

    const setPreviewHeaderOffset = () => {
        const header = document.querySelector('[data-site-header]');
        const offset = header ? Math.max(0, header.getBoundingClientRect().bottom) : 0;
        root.style.setProperty('--page-transition-header-height', `${offset}px`);
    };

    const startPreviewTransition = (destination, direction) => {
        const stage = document.createElement('div');
        const frame = document.createElement('iframe');
        let finished = false;
        let animationStarted = false;
        let loadTimer;
        let readinessTimer;

        previewStage = stage;
        stage.className = `page-transition-preview page-transition-preview--${direction}`;
        stage.setAttribute('aria-hidden', 'true');
        frame.className = 'page-transition-preview__frame';
        frame.setAttribute('sandbox', 'allow-same-origin');
        frame.setAttribute('tabindex', '-1');
        frame.setAttribute('title', 'Anteprima della pagina richiesta');
        frame.src = destination.href;
        stage.append(frame);

        const finishNavigation = () => {
            if (finished) return;
            finished = true;
            window.clearTimeout(loadTimer);
            window.clearTimeout(readinessTimer);
            safeStorage.set(previewedKey, JSON.stringify({
                createdAt: Date.now(),
                url: destination.href,
            }));
            window.location.assign(destination.href);
        };

        const beginAnimation = () => {
            if (finished || animationStarted) return;
            if (!preparePreviewDocument(frame, destination)) {
                finished = true;
                window.clearTimeout(loadTimer);
                window.clearTimeout(readinessTimer);
                navigateWithFallback(destination, direction);
                return;
            }

            animationStarted = true;
            window.clearTimeout(loadTimer);
            window.clearTimeout(readinessTimer);
            root.classList.add('page-transition-previewing');
            root.setAttribute('aria-busy', 'true');
            setPreviewHeaderOffset();

            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    stage.classList.add('is-running');
                });
            });
            window.setTimeout(finishNavigation, previewDuration);
        };

        const checkReadiness = () => {
            if (finished || animationStarted) return;
            try {
                if (previewAssetsReady(frame)) {
                    beginAnimation();
                    return;
                }
            } catch (_error) {
                // Il normale evento load o il timeout mantengono disponibile la navigazione.
            }
            readinessTimer = window.setTimeout(checkReadiness, 30);
        };

        frame.addEventListener('load', checkReadiness, { once: true });
        frame.addEventListener('error', () => {
            if (finished) return;
            finished = true;
            window.clearTimeout(loadTimer);
            window.clearTimeout(readinessTimer);
            navigateWithFallback(destination, direction);
        }, { once: true });

        document.body.append(stage);
        readinessTimer = window.setTimeout(checkReadiness, 30);
        loadTimer = window.setTimeout(() => {
            if (finished) return;
            finished = true;
            window.clearTimeout(readinessTimer);
            navigateWithFallback(destination, direction);
        }, previewLoadTimeout);
    };

    document.addEventListener('click', (event) => {
        const anchor = event.target.closest?.('a[href]');
        if (!anchor) return;

        let destination;
        try {
            destination = new URL(anchor.href, window.location.href);
        } catch (_error) {
            return;
        }
        if (!shouldTransition(event, anchor, destination)) return;

        event.preventDefault();
        navigationStarted = true;
        const returningHome = destination.pathname === '/' && window.location.pathname !== '/';
        const direction = returningHome ? 'backward' : 'forward';
        safeStorage.set(activeIndexKey, String(currentIndex));
        try {
            startPreviewTransition(destination, direction);
        } catch (_error) {
            navigateWithFallback(destination, direction);
        }
    });
})();
