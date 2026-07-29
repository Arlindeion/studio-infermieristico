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
    const titolo = document.getElementById('cal-titolo');
    const griglia = document.getElementById('cal-griglia');
    const dettaglio = document.getElementById('cal-dettaglio');
    const precedente = document.getElementById('btn-prec');
    const successivo = document.getElementById('btn-succ');

    if (!titolo || !griglia || !dettaglio || !precedente || !successivo) {
        return;
    }

    const corsiMap = {};
    corsi.forEach(c => { corsiMap[c.data] = c; });

    const mesiNomi = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
                      'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];

    const oggi = new Date();
    let anno = oggi.getFullYear();
    let mese = oggi.getMonth();
    let pulsanteAttivo = null;

    const dateOrdinate = corsi
        .map(corso => corso.data)
        .filter(Boolean)
        .sort();
    const oggiLocale = [
        oggi.getFullYear(),
        String(oggi.getMonth() + 1).padStart(2, '0'),
        String(oggi.getDate()).padStart(2, '0')
    ].join('-');
    const prossimaData = dateOrdinate.find(data => data >= oggiLocale) || dateOrdinate[0];

    if (prossimaData) {
        const [annoCorso, meseCorso] = prossimaData.split('-').map(Number);
        anno = annoCorso;
        mese = meseCorso - 1;
    }

    function renderCalendario() {
        titolo.textContent = mesiNomi[mese] + ' ' + anno;
        griglia.innerHTML = '';
        dettaglio.style.display = 'none';
        pulsanteAttivo = null;

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

            if (dataStr === oggiLocale) {
                cella.classList.add('oggi');
            }

            if (corsiMap[dataStr]) {
                const pulsante = document.createElement('button');
                pulsante.type = 'button';
                pulsante.classList.add('cal-cella', 'ha-corso');
                if (dataStr === oggiLocale) {
                    pulsante.classList.add('oggi');
                }
                pulsante.textContent = g;
                pulsante.setAttribute('aria-expanded', 'false');
                pulsante.setAttribute(
                    'aria-label',
                    `${g} ${mesiNomi[mese]} ${anno}: ${corsiMap[dataStr].titolo}. Mostra i dettagli`
                );
                pulsante.addEventListener('click', () => mostraDettaglio(corsiMap[dataStr], pulsante));
                griglia.appendChild(pulsante);
                continue;
            }

            griglia.appendChild(cella);
        }
    }

    function mostraDettaglio(corso, pulsante) {
        if (pulsanteAttivo && pulsanteAttivo !== pulsante) {
            pulsanteAttivo.setAttribute('aria-expanded', 'false');
        }
        pulsanteAttivo = pulsante;
        pulsante.setAttribute('aria-expanded', 'true');
        document.getElementById('det-titolo').textContent = corso.titolo;
        document.getElementById('det-ora').textContent = corso.ora ? 'Orario: ' + corso.ora : '';
        document.getElementById('det-luogo').textContent = corso.luogo ? 'Luogo: ' + corso.luogo : '';
        document.getElementById('det-descrizione').textContent = corso.descrizione || '';
        dettaglio.style.display = 'block';
    }

    precedente.addEventListener('click', () => {
        mese--; if (mese < 0) { mese = 11; anno--; }
        renderCalendario();
    });

    successivo.addEventListener('click', () => {
        mese++; if (mese > 11) { mese = 0; anno++; }
        renderCalendario();
    });

    renderCalendario();
});
