document.addEventListener('DOMContentLoaded', function() {
    const analyticsMeta = document.querySelector('meta[name="google-analytics-id"]');
    const preferencesButton = document.getElementById('cookie-preferences');
    const measurementId = analyticsMeta ? analyticsMeta.content.trim() : '';
    const storageKey = 'sc_analytics_consent';
    const deniedConsent = {
        analytics_storage: 'denied',
        ad_storage: 'denied',
        ad_user_data: 'denied',
        ad_personalization: 'denied'
    };

    if (!measurementId) {
        return;
    }

    function readChoice() {
        try {
            return localStorage.getItem(storageKey);
        } catch (error) {
            return null;
        }
    }

    function storeChoice(choice) {
        try {
            localStorage.setItem(storageKey, choice);
        } catch (error) {
            // La scelta resta valida per la pagina corrente anche quando il
            // browser impedisce l'accesso allo storage.
        }
    }

    function updateConsent(analyticsStorage) {
        if (typeof window.gtag !== 'function') {
            return;
        }
        window.gtag('consent', 'update', {
            ...deniedConsent,
            analytics_storage: analyticsStorage
        });
    }

    function removeAnalyticsCookies() {
        document.cookie.split(';').forEach(function(cookie) {
            const name = cookie.split('=')[0].trim();
            if (!/^_ga(?:_|$)|^_gid$|^_gat(?:_|$)/.test(name)) {
                return;
            }
            document.cookie = name + '=; Max-Age=0; path=/; SameSite=Lax';
        });
    }

    function loadGoogleAnalytics() {
        if (window.gtag) {
            updateConsent('granted');
            return;
        }

        window.dataLayer = window.dataLayer || [];
        window.gtag = function() {
            window.dataLayer.push(arguments);
        };
        window.gtag('consent', 'default', deniedConsent);

        const script = document.createElement('script');
        script.async = true;
        script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(measurementId);
        document.head.appendChild(script);

        updateConsent('granted');
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
        storeChoice(choice);
        removeBanner();

        if (choice === 'accepted') {
            loadGoogleAnalytics();
        } else {
            updateConsent('denied');
            removeAnalyticsCookies();
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

    const savedChoice = readChoice();

    if (savedChoice === 'accepted') {
        loadGoogleAnalytics();
    } else if (savedChoice !== 'rejected') {
        showBanner();
    }
});
