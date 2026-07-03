// Gestione del calendario e dei dati dei corsi per la homepage
// I dati dei corsi vengono letti dal blocco <script id="corsi-data" type="application/json">
// presente nella homepage, così da evitare script inline (non ammessi dalla CSP).
document.addEventListener('DOMContentLoaded', function() {
    let corsi = [];
    const datiElemento = document.getElementById('corsi-data');
    if (datiElemento) {
        try {
            corsi = JSON.parse(datiElemento.textContent);
        } catch (errore) {
            console.error('Errore nel parsing dei dati dei corsi:', errore);
        }
    }
    const corsiMap = {};
    corsi.forEach(c => { corsiMap[c.data] = c; });

    const mesiNomi = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
                      'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];

    let oggi = new Date();
    let anno = oggi.getFullYear();
    let mese = oggi.getMonth();

    function renderCalendario() {
        const titolo = document.getElementById('cal-titolo');
        const griglia = document.getElementById('cal-griglia');
        const dettaglio = document.getElementById('cal-dettaglio');

        titolo.textContent = mesiNomi[mese] + ' ' + anno;
        griglia.innerHTML = '';
        dettaglio.style.display = 'none';

        const primoGiorno = new Date(anno, mese, 1).getDay();
        const offsetLun = (primoGiorno === 0) ? 6 : primoGiorno - 1;
        const giorniNelMese = new Date(anno, mese + 1, 0).getDate();

        for (let i = 0; i < offsetLun; i++) {
            const vuoto = document.createElement('div');
            vuoto.classList.add('cal-cella', 'vuota');
            griglia.appendChild(vuoto);
        }

        for (let g = 1; g <= giorniNelMese; g++) {
            const mm = String(mese + 1).padStart(2, '0');
            const gg = String(g).padStart(2, '0');
            const dataStr = `${anno}-${mm}-${gg}`;

            const cella = document.createElement('div');
            cella.classList.add('cal-cella');
            cella.textContent = g;

            if (dataStr === oggi.toISOString().split('T')[0]) {
                cella.classList.add('oggi');
            }

            if (corsiMap[dataStr]) {
                cella.classList.add('ha-corso');
                cella.title = corsiMap[dataStr].titolo;
                cella.addEventListener('click', () => mostraDettaglio(corsiMap[dataStr]));
            }

            griglia.appendChild(cella);
        }
    }

    function mostraDettaglio(corso) {
        const det = document.getElementById('cal-dettaglio');
        document.getElementById('det-titolo').textContent = corso.titolo;
        document.getElementById('det-ora').textContent = corso.ora ? '🕐 ' + corso.ora : '';
        document.getElementById('det-luogo').textContent = corso.luogo ? '📍 ' + corso.luogo : '';
        document.getElementById('det-descrizione').textContent = corso.descrizione || '';
        det.style.display = 'block';
    }

    document.getElementById('btn-prec').addEventListener('click', () => {
        mese--; if (mese < 0) { mese = 11; anno--; }
        renderCalendario();
    });

    document.getElementById('btn-succ').addEventListener('click', () => {
        mese++; if (mese > 11) { mese = 0; anno++; }
        renderCalendario();
    });

    renderCalendario();
});