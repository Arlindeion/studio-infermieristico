document.addEventListener('DOMContentLoaded', function() {
    const navigation = document.querySelector('.admin-shell-nav');
    if (!navigation) return;

    function revealActiveSection() {
        const active = navigation.querySelector('.admin-shell-nav-link.attivo');
        if (!active || navigation.scrollWidth <= navigation.clientWidth) return;
        active.scrollIntoView({
            behavior: 'auto',
            block: 'nearest',
            inline: 'center',
        });
    }

    revealActiveSection();
    navigation.addEventListener('click', function(event) {
        if (!event.target.closest('.admin-shell-nav-link')) return;
        window.requestAnimationFrame(revealActiveSection);
    });
});
