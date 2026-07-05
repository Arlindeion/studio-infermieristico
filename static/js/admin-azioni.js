// Azioni admin: conferma le azioni per appuntamenti e corsi
document.addEventListener('DOMContentLoaded', function() {
    // Gestisce i link di azione per gli appuntamenti (conferma, modifica, elimina, ecc.)
    document.querySelectorAll('.btn-azione').forEach(pulsante => {
        // Elabora solo i tag <a> (collegamenti)
        if (tagNameCheck(pulsante, 'a')) {
            pulsante.addEventListener('click', function(e) {
                const messaggio = this.getAttribute('data-confirm');
                if (messaggio && !confirm(messaggio)) {
                    e.preventDefault();
                }
                // Se confermato, il browser seguirà naturalmente il collegamento.
            });
        }
    });

    // Funzione ausiliaria per controllare il nome del tag (case-insensitive)
    function tagNameCheck(elemento, nomeTag) {
        return elemento.tagName.toLowerCase() === nomeTag.toLowerCase();
    }
});
