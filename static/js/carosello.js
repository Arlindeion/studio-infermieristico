// Funzionalità della carosella per la homepage
document.addEventListener('DOMContentLoaded', function() {
    let indice = 0;
    const imgs = document.querySelectorAll('.carosello-traccia img');
    const dotsContainer = document.getElementById('dots');
    const btnPrev = document.querySelector('.carosello-btn.prev');
    const btnNext = document.querySelector('.carosello-btn.next');

    // Creare i puntini
    imgs.forEach((_, i) => {
        const dot = document.createElement('span');
        dot.classList.add('dot');
        if (i === 0) dot.classList.add('attivo');
        dot.addEventListener('click', () => vaiA(i));
        dotsContainer.appendChild(dot);
    });

    function vaiA(n) {
        imgs[indice].classList.remove('attiva');
        document.querySelectorAll('.dot')[indice].classList.remove('attivo');
        indice = (n + imgs.length) % imgs.length;
        imgs[indice].classList.add('attiva');
        document.querySelectorAll('.dot')[indice].classList.add('attivo');
    }

    function spostaCarosello(direzione) {
        vaiA(indice + direzione);
    }

    // Ascoltatori di eventi per i pulsanti
    if (btnPrev) {
        btnPrev.addEventListener('click', () => spostaCarosello(-1));
    }
    if (btnNext) {
        btnNext.addEventListener('click', () => spostaCarosello(1));
    }

    // Inizializzare la prima diapositiva
    imgs[0].classList.add('attiva');

    // Avanzamento automatico ogni 4 secondi
    let autoPlayInterval = setInterval(() => spostaCarosello(1), 4000);

    // ─── GESTIONE DELLO SCORRIMENTO SU DISPOSITIVI MOBILI ───
    const carosello = document.querySelector('.carosello');
    let touchStartX = 0;
    let touchEndX = 0;

    carosello.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    carosello.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        const diff = touchStartX - touchEndX;
        if (Math.abs(diff) > 50) {
            // Sospendere la riproduzione automatica durante l'interazione utente
            clearInterval(autoPlayInterval);
            spostaCarosello(diff > 0 ? 1 : -1);
            // Riavviare la riproduzione automatica dopo un ritardo (opzionale)
            // setTimeout(() => { autoPlayInterval = setInterval(() => spostaCarosello(1), 4000); }, 8000);
        }
    }, { passive: true });

    // Opzionale: mettere in pausa la riproduzione automatica quando l'utente interagisce con i puntini o tocca
    // Potremmo aggiungere ascoltatori di eventi ai puntini per mettere in pausa l'autoplay, ma per semplicità lasciamo così.
});