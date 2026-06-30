// Funzionalità del menu mobile
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const navMobile = document.getElementById('nav-mobile');

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
});