document.addEventListener('DOMContentLoaded', function() {
    const analyticsMeta = document.querySelector('meta[name="google-analytics-id"]');
    const preferencesButton = document.getElementById('cookie-preferences');
    const measurementId = analyticsMeta ? analyticsMeta.content.trim() : '';
    const storageKey = 'sc_analytics_consent';

    if (!measurementId) {
        return;
    }

    function loadGoogleAnalytics() {
        if (window.gtag) {
            return;
        }

        window.dataLayer = window.dataLayer || [];
        window.gtag = function() {
            window.dataLayer.push(arguments);
        };

        const script = document.createElement('script');
        script.async = true;
        script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(measurementId);
        document.head.appendChild(script);

        window.gtag('js', new Date());
        window.gtag('config', measurementId, {
            anonymize_ip: true
        });
    }

    function removeBanner() {
        const existingBanner = document.querySelector('.cookie-banner');
        if (existingBanner) {
            existingBanner.remove();
        }
    }

    function saveChoice(choice) {
        localStorage.setItem(storageKey, choice);
        removeBanner();

        if (choice === 'accepted') {
            loadGoogleAnalytics();
        }
    }

    function showBanner() {
        removeBanner();

        const banner = document.createElement('div');
        banner.className = 'cookie-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-live', 'polite');
        banner.setAttribute('aria-label', 'Preferenze cookie');

        banner.innerHTML = [
            '<div class="cookie-banner-text">',
            '<strong>Cookie e statistiche</strong>',
            '<p>Usiamo Google Analytics solo con il tuo consenso per capire quali pagine vengono consultate e migliorare il sito. I cookie tecnici restano sempre attivi.</p>',
            '</div>',
            '<div class="cookie-banner-actions">',
            '<button type="button" class="btn-cookie btn-cookie-secondary" data-cookie-choice="rejected">Rifiuta</button>',
            '<button type="button" class="btn-cookie btn-cookie-primary" data-cookie-choice="accepted">Accetta statistiche</button>',
            '</div>'
        ].join('');

        banner.addEventListener('click', function(event) {
            const choiceButton = event.target.closest('[data-cookie-choice]');
            if (!choiceButton) {
                return;
            }

            saveChoice(choiceButton.dataset.cookieChoice);
        });

        document.body.appendChild(banner);
    }

    if (preferencesButton) {
        preferencesButton.addEventListener('click', showBanner);
    }

    const savedChoice = localStorage.getItem(storageKey);

    if (savedChoice === 'accepted') {
        loadGoogleAnalytics();
    } else if (!savedChoice) {
        showBanner();
    }
});
