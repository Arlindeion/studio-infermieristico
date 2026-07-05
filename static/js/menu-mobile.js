// Funzionalità del menu mobile
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const navMobile = document.getElementById('nav-mobile');
    const dropdowns = document.querySelectorAll('.nav-dropdown');

    if (hamburger && navMobile) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('aperto');
            navMobile.classList.toggle('aperto');
        });

        function chiudiMenu() {
            if (hamburger && navMobile) {
                hamburger.classList.remove('aperto');
                navMobile.classList.remove('aperto');
            }
        }

        // Chiudi il menu quando si clicca su un link di navigazione nel menu mobile
        navMobile.addEventListener('click', (e) => {
            if (e.target.tagName === 'A') {
                chiudiMenu();
            }
        });

        // Chiudi il menu quando si clicca su un link di navigazione desktop (header)
        const navDesktopLinks = document.querySelectorAll('.nav-desktop a');
        navDesktopLinks.forEach(link => {
            link.addEventListener('click', chiudiMenu);
        });

        document.addEventListener('click', (e) => {
            if (!hamburger.contains(e.target) && !navMobile.contains(e.target)) {
                chiudiMenu();
            }
        });
    }

    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.nav-dropdown-toggle');
        if (!toggle) {
            return;
        }

        toggle.addEventListener('click', event => {
            event.stopPropagation();
            const giaAperto = dropdown.classList.contains('aperto');
            dropdowns.forEach(item => {
                item.classList.remove('aperto');
                const itemToggle = item.querySelector('.nav-dropdown-toggle');
                if (itemToggle) {
                    itemToggle.setAttribute('aria-expanded', 'false');
                }
            });
            dropdown.classList.toggle('aperto', !giaAperto);
            toggle.setAttribute('aria-expanded', giaAperto ? 'false' : 'true');
        });
    });

    document.addEventListener('click', event => {
        dropdowns.forEach(dropdown => {
            if (!dropdown.contains(event.target)) {
                dropdown.classList.remove('aperto');
                const toggle = dropdown.querySelector('.nav-dropdown-toggle');
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'false');
                }
            }
        });
    });
});
