document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('[data-site-header]');
    const desktopNav = document.querySelector('[data-desktop-nav]');
    const dropdown = document.querySelector('[data-nav-dropdown]');
    const dropdownToggle = document.querySelector('[data-nav-dropdown-toggle]');
    const dropdownPanel = document.querySelector('[data-nav-dropdown-panel]');
    const menuToggle = document.querySelector('[data-menu-toggle]');
    const mobileNav = document.querySelector('[data-mobile-nav]');
    const mobileCoursesToggle = document.querySelector('[data-mobile-courses-toggle]');
    const mobileCoursesList = document.querySelector('[data-mobile-courses-list]');
    const desktopMedia = window.matchMedia('(min-width: 1121px)');
    let lastFocusedElement = null;
    let resizeFrame = null;
    let scrollFrame = null;

    function setDropdown(open) {
        if (!dropdown || !dropdownToggle || !dropdownPanel) {
            return;
        }

        dropdown.classList.toggle('is-open', open);
        dropdownToggle.setAttribute('aria-expanded', String(open));
        dropdownPanel.setAttribute('aria-hidden', String(!open));
        if (open) {
            dropdownPanel.removeAttribute('inert');
        } else {
            dropdownPanel.setAttribute('inert', '');
        }
    }

    if (dropdownToggle) {
        dropdownToggle.addEventListener('click', (event) => {
            event.stopPropagation();
            setDropdown(dropdownToggle.getAttribute('aria-expanded') !== 'true');
        });
    }

    document.addEventListener('click', (event) => {
        if (dropdown && !dropdown.contains(event.target)) {
            setDropdown(false);
        }
    });

    function moveThread(target) {
        if (!desktopNav || !target) {
            if (desktopNav) {
                desktopNav.classList.remove('has-thread');
            }
            return;
        }

        const navRect = desktopNav.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        desktopNav.style.setProperty('--thread-x', `${targetRect.left - navRect.left}px`);
        desktopNav.style.setProperty('--thread-width', `${targetRect.width}px`);
        desktopNav.classList.add('has-thread');
    }

    if (desktopNav) {
        const navItems = Array.from(desktopNav.querySelectorAll('[data-nav-item]'));
        const currentItem = desktopNav.querySelector('[data-nav-current]');
        const restoreThread = () => moveThread(currentItem);

        navItems.forEach((item) => {
            item.addEventListener('pointerenter', () => moveThread(item));
            item.addEventListener('focus', () => moveThread(item));
        });

        desktopNav.addEventListener('pointerleave', restoreThread);
        desktopNav.addEventListener('focusout', (event) => {
            if (!desktopNav.contains(event.relatedTarget)) {
                restoreThread();
            }
        });

        requestAnimationFrame(restoreThread);
        window.addEventListener('resize', () => {
            if (resizeFrame) {
                cancelAnimationFrame(resizeFrame);
            }
            resizeFrame = requestAnimationFrame(restoreThread);
        });
    }

    function focusableElements() {
        if (!mobileNav) {
            return [];
        }

        return Array.from(mobileNav.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'))
            .filter((element) => !element.closest('[inert]'));
    }

    function setMobileMenu(open, restoreFocus = true) {
        if (!menuToggle || !mobileNav) {
            return;
        }

        const menuText = menuToggle.querySelector('.menu-toggle__text');
        menuToggle.setAttribute('aria-expanded', String(open));
        menuToggle.setAttribute('aria-label', open ? 'Chiudi il menu' : 'Apri il menu');
        if (menuText) {
            menuText.textContent = open ? 'Chiudi' : 'Menu';
        }

        document.body.classList.toggle('menu-open', open);
        mobileNav.setAttribute('aria-hidden', String(!open));

        if (open) {
            lastFocusedElement = document.activeElement;
            mobileNav.removeAttribute('inert');
            requestAnimationFrame(() => {
                mobileNav.classList.add('is-open');
                const firstTarget = mobileNav.querySelector('.mobile-nav__pillar');
                if (firstTarget) {
                    firstTarget.focus();
                }
            });
            return;
        }

        mobileNav.classList.remove('is-open');
        mobileNav.setAttribute('inert', '');
        if (restoreFocus && lastFocusedElement && document.contains(lastFocusedElement)) {
            lastFocusedElement.focus();
        }
        lastFocusedElement = null;
    }

    if (menuToggle && mobileNav) {
        menuToggle.addEventListener('click', () => {
            setMobileMenu(menuToggle.getAttribute('aria-expanded') !== 'true');
        });

        const closeButton = mobileNav.querySelector('[data-menu-close]');
        if (closeButton) {
            closeButton.addEventListener('click', () => setMobileMenu(false));
        }

        mobileNav.addEventListener('click', (event) => {
            if (event.target.closest('a')) {
                setMobileMenu(false, false);
            }
        });
    }

    if (mobileCoursesToggle && mobileCoursesList) {
        mobileCoursesToggle.addEventListener('click', () => {
            const open = mobileCoursesToggle.getAttribute('aria-expanded') !== 'true';
            mobileCoursesToggle.setAttribute('aria-expanded', String(open));
            mobileCoursesList.setAttribute('aria-hidden', String(!open));
            mobileCoursesList.classList.toggle('is-open', open);
            if (open) {
                mobileCoursesList.removeAttribute('inert');
            } else {
                mobileCoursesList.setAttribute('inert', '');
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        const mobileMenuOpen = menuToggle && menuToggle.getAttribute('aria-expanded') === 'true';

        if (event.key === 'Escape') {
            if (mobileMenuOpen) {
                setMobileMenu(false);
                return;
            }

            if (dropdownToggle && dropdownToggle.getAttribute('aria-expanded') === 'true') {
                setDropdown(false);
                dropdownToggle.focus();
            }
        }

        if (event.key !== 'Tab' || !mobileMenuOpen) {
            return;
        }

        const focusables = focusableElements();
        if (!focusables.length) {
            return;
        }

        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });

    desktopMedia.addEventListener('change', (event) => {
        if (event.matches) {
            setMobileMenu(false, false);
        } else {
            setDropdown(false);
        }
    });

    function updateHeaderState() {
        if (header) {
            header.classList.toggle('is-scrolled', window.scrollY > 16);
        }
        scrollFrame = null;
    }

    window.addEventListener('scroll', () => {
        if (!scrollFrame) {
            scrollFrame = requestAnimationFrame(updateHeaderState);
        }
    }, { passive: true });

    updateHeaderState();
});
