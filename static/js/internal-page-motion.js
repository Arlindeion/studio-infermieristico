(() => {
    'use strict';

    const clamp = (value, minimum = 0, maximum = 1) => (
        Math.min(maximum, Math.max(minimum, value))
    );

    document.addEventListener('DOMContentLoaded', () => {
        const body = document.querySelector('[data-internal-page]');
        const main = document.querySelector('#contenuto-principale');
        if (!body || !main) return;

        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        const arrivedThroughPreview = document.documentElement.classList.contains('page-transition-arrived');
        const mode = body.dataset.internalPage;
        const progress = document.querySelector('[data-internal-progress]');
        let scrollFrame = null;

        const updateProgress = () => {
            scrollFrame = null;
            if (!progress) return;

            const availableScroll = document.documentElement.scrollHeight - window.innerHeight;
            const value = availableScroll > 0 ? clamp(window.scrollY / availableScroll) : 1;
            progress.style.setProperty('--internal-progress', String(value));
        };

        const requestProgressUpdate = () => {
            if (scrollFrame) return;
            scrollFrame = requestAnimationFrame(updateProgress);
        };

        if (progress) {
            updateProgress();
            window.addEventListener('scroll', requestProgressUpdate, { passive: true });
            window.addEventListener('resize', requestProgressUpdate);
        }

        const stickyBar = document.querySelector('.sticky-prenota');
        const stickyLink = stickyBar?.querySelector('a[href]');
        if (stickyBar && stickyLink && 'IntersectionObserver' in window) {
            const href = stickyLink.getAttribute('href');
            const matchingActions = Array.from(main.querySelectorAll('a[href]')).filter((link) => (
                link.getAttribute('href') === href
            ));
            const destination = href?.startsWith('#') ? document.querySelector(href) : null;
            const stickyTargets = [...new Set([...matchingActions, destination].filter(Boolean))];
            const visibleTargets = new Set();
            const stickyObserver = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        visibleTargets.add(entry.target);
                    } else {
                        visibleTargets.delete(entry.target);
                    }
                });
                stickyBar.classList.toggle('is-context-hidden', visibleTargets.size > 0);
            }, { threshold: 0.18 });
            stickyTargets.forEach((target) => stickyObserver.observe(target));
        }

        if (reducedMotion.matches) {
            body.classList.add('internal-motion-reduced');
            return;
        }

        const pageRoot = main.firstElementChild;
        if (!pageRoot) return;

        const mainSections = Array.from(main.children).filter((child) => (
            child.matches('section, article, aside')
        ));
        const candidates = mainSections.length ? [...mainSections] : [pageRoot];
        if (mode === 'narrative' && mainSections.length <= 1) {
            Array.from(pageRoot.children).forEach((child) => {
                if (child.matches('section, article, aside, figure, .chi-siamo-contenuto, .valori, .profile-next-step, .faq-list, .faq-cta, .course-overview-strip, .course-directory, .course-flow, .privacy-contenuto, .nursing-facts, .nursing-catalog, .nursing-visit-grid, .studio-location')) {
                    candidates.push(child);
                }
            });
        }

        const revealTargets = [...new Set(candidates)];
        revealTargets.forEach((element, index) => {
            element.dataset.internalReveal = index === 0 ? 'hero' : 'chapter';
        });

        if (arrivedThroughPreview) {
            revealTargets.forEach((element) => {
                const bounds = element.getBoundingClientRect();
                if (bounds.top < window.innerHeight && bounds.bottom > 0) {
                    element.classList.add('is-internal-visible');
                }
            });
        }
        body.classList.add('internal-motion-ready');
        if (!arrivedThroughPreview) {
            revealTargets[0]?.classList.add('is-internal-visible');
        }

        if (!('IntersectionObserver' in window)) {
            revealTargets.forEach((element) => element.classList.add('is-internal-visible'));
            return;
        }

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-internal-visible');
                observer.unobserve(entry.target);
            });
        }, {
            rootMargin: '0px 0px -12% 0px',
            threshold: 0.08,
        });

        revealTargets.slice(1).forEach((element) => observer.observe(element));
    });
})();
