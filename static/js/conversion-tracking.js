document.addEventListener('click', function (event) {
    const link = event.target.closest('[data-conversion]');
    let analyticsAccepted = false;
    try {
        analyticsAccepted = localStorage.getItem('sc_analytics_consent') === 'accepted';
    } catch (error) {
        analyticsAccepted = false;
    }
    if (!link || !analyticsAccepted || typeof window.gtag !== 'function') return;

    window.gtag('event', 'conversion_click', {
        conversion_name: link.dataset.conversion,
        link_url: link.href || '',
        page_path: window.location.pathname
    });
});
