import os
import sys
import pytest
import icalendar
from unittest.mock import MagicMock, patch
from datetime import date, datetime

# Assicurarsi che l'applicazione possa essere importata
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import app as flask_app
from config import config
from app import (
    db,
    Appuntamento,
    Admin,
    Corso,
    IscrizioneCorso,
    PersonaCorso,
    PercorsoAccompagnamento,
    IncontroAccompagnamento,
    PresenzaAccompagnamento,
)

@pytest.fixture
def app():
    """Crea e configura una nuova istanza dell'app per ogni test."""
    # Utilizzare la configurazione di test
    flask_app.config.from_object(config['testing'])
    # Stabilire un contesto applicativo
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Un client di test per l'app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Un runner di test per i comandi Click dell'app."""
    return app.test_cli_runner()

def test_app_exists(app):
    """Controllo di sanità che l'app esista."""
    assert app is not None

def test_app_is_testing(app):
    """Assicurarsi che l'app sia in modalità di test."""
    assert app.config['TESTING'] == True

def test_database_empty(app):
    """Iniziare con un database vuoto."""
    with app.app_context():
        assert Appuntamento.query.count() == 0
        assert Admin.query.count() == 0
        assert Corso.query.count() == 0
        assert IscrizioneCorso.query.count() == 0
        assert PersonaCorso.query.count() == 0
        assert PercorsoAccompagnamento.query.count() == 0
        assert IncontroAccompagnamento.query.count() == 0
        assert PresenzaAccompagnamento.query.count() == 0

def test_create_admin(app):
    """Testare che un amministratore possa essere creato."""
    with app.app_context():
        admin = Admin(username='testadmin', password='hashed')
        db.session.add(admin)
        db.session.commit()
        assert Admin.query.filter_by(username='testadmin').first() is not None

def test_create_appointment(app):
    """Testare la creazione di un appuntamento."""
    with app.app_context():
        appt = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Iniezione intramuscolare',
            data='2026-07-01',
            ora='10:00',
            note='Nessuna'
        )
        db.session.add(appt)
        db.session.commit()
        saved = Appuntamento.query.filter_by(email='mario@example.com').first()
        assert saved is not None
        assert saved.nome == 'Mario Rossi'
        assert saved.stato == 'In attesa'  # predefinito

def test_orari_occupati_endpoint(client):
    """Testare l'endpoint /api/orari-occupati/<data>."""
    with flask_app.app_context():
        # Inserire un appuntamento per una data specifica
        appt = Appuntamento(
            nome='Test User',
            telefono='123',
            email='test@test.com',
            servizio='Test',
            data='2026-07-10',
            ora='10:30',
            stato='Confermato'
        )
        db.session.add(appt)
        db.session.commit()
        # Richiedere l'endpoint
        resp = client.get('/api/orari-occupati/2026-07-10')
        assert resp.status_code == 200
        data = resp.get_json()
        assert '10:30' in data
        # Assicurarsi che gli appuntamenti annullati non siano inclusi
        appt.stato = 'Annullato'
        db.session.commit()
        resp2 = client.get('/api/orari-occupati/2026-07-10')
        data2 = resp2.get_json()
        assert '10:30' not in data2  # dovrebbe essere libero dopo la cancellazione

def test_holiday_flow(client):
    """Semplice test della home page."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'S.C. Studio Infermieristico' in resp.data  # adeguare in base al contenuto effettivo
    assert 'href="/faq">FAQ</a>' in resp.text


def test_faq_include_flussi_aggiornati(client):
    resp = client.get('/faq')
    assert resp.status_code == 200
    assert 'SOS neomamma' in resp.text
    assert 'BLSD' in resp.text
    assert 'link privato' in resp.text
    assert 'open day gratuito' in resp.text


def _prossimo_giorno_con_weekday(weekday):
    giorno = date.today()
    giorni_da_aggiungere = (weekday - giorno.weekday()) % 7
    if giorni_da_aggiungere == 0:
        giorni_da_aggiungere = 7
    return giorno + app_module.timedelta(days=giorni_da_aggiungere)


def _prossimo_sabato_non_festivo():
    giorno = _prossimo_giorno_con_weekday(5)
    while app_module.is_festivo(giorno):
        giorno += app_module.timedelta(days=7)
    return giorno


def _csrf_prenota(client):
    import re
    resp = client.get('/prenota')
    return re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)


def _csrf_iscrizione(client, corso_tipo):
    import re
    resp = client.get(f'/iscrizione-corsi/{corso_tipo}')
    return re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)


def _crea_data_corso(corso_tipo, titolo='Corso test', data='2099-07-16', ora='18:00', luogo='Studio'):
    with flask_app.app_context():
        corso = Corso(
            titolo=titolo,
            tipo=corso_tipo,
            descrizione='Data aperta per test',
            data=data,
            ora=ora,
            luogo=luogo,
            durata_ore=2,
        )
        db.session.add(corso)
        db.session.commit()
        return str(corso.id)


def _crea_percorso_accompagnamento(slug='percorso-test', incontri=9):
    with flask_app.app_context():
        percorso = PercorsoAccompagnamento(
            titolo='Iscrizione al corso',
            slug=slug,
            descrizione='Edizione privata test',
            capienza_coppie=8,
            luogo='Studio',
            contatti='3806317175',
            stato='Aperto',
        )
        db.session.add(percorso)
        db.session.flush()
        professionisti = ['Infermiera', 'Ostetrica', 'Psicologa', 'Osteopata', 'Nutrizionista']
        for numero in range(1, incontri + 1):
            db.session.add(IncontroAccompagnamento(
                percorso=percorso,
                numero=numero,
                data=f'2099-08-{numero:02d}',
                ora='17:00',
                professionista=professionisti[(numero - 1) % len(professionisti)],
                tema=f'Incontro {numero}',
                luogo='Studio',
            ))
        db.session.commit()
        return percorso.slug, percorso.id


def test_iscrizione_disostruzione_salva_richiesta(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'nome_bambino': 'Luca',
        'eta_bambino': '3 anni',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/conferma'
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.corso_tipo == 'disostruzione-pediatrica'
        assert iscrizione.nome == 'Mario Rossi'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'richiesta_iscrizione'
        assert iscrizione.posti == 1
        assert iscrizione.persona is not None
        assert iscrizione.persona.nome_bambino == 'Luca'
        assert iscrizione.persona.eta_bambino == '3 anni'
        assert iscrizione.extra_dict()['nome_bambino'] == 'Luca'
        assert '16/07/2099' in iscrizione.data_corso
        assert iscrizione.stato == 'Nuova'
        assert PersonaCorso.query.count() == 1


def test_iscrizione_blsd_salva_richiesta_individuale(client):
    data_corso_id = _crea_data_corso('bls-d', 'Corso BLSD', data='2099-07-17', ora='09:00')
    token = _csrf_iscrizione(client, 'bls-d')

    resp = client.post('/iscrizione-corsi/bls-d', data={
        'nome': 'Giulia Bianchi',
        'codice_fiscale': 'BNCGLI85A41G482Z',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'partecipazione': 'Iscrizione individuale',
        'data_corso': data_corso_id,
        'prove_pratiche': 'on',
        'buono_stato_salute': 'on',
        'richiesta_non_conferma': 'on',
        'consenso_privacy': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/conferma'
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        extra = iscrizione.extra_dict()
        assert iscrizione.corso_tipo == 'bls-d'
        assert iscrizione.corso_titolo == 'Corso BLSD'
        assert iscrizione.partecipazione == 'Iscrizione individuale'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'richiesta_iscrizione'
        assert iscrizione.posti == 1
        assert '17/07/2099' in iscrizione.data_corso
        assert not iscrizione.consenso_immagini
        assert 'ente_azienda' not in extra
        assert 'numero_partecipanti' not in extra


def test_iscrizione_blsd_non_accetta_azienda_da_form(client):
    data_corso_id = _crea_data_corso('bls-d', 'Corso BLSD', data='2099-07-17', ora='09:00')
    token = _csrf_iscrizione(client, 'bls-d')

    resp = client.post('/iscrizione-corsi/bls-d', data={
        'nome': 'Giulia Bianchi',
        'codice_fiscale': 'BNCGLI85A41G482Z',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'partecipazione': 'Azienda o gruppo',
        'data_corso': data_corso_id,
        'prove_pratiche': 'on',
        'buono_stato_salute': 'on',
        'richiesta_non_conferma': 'on',
        'consenso_privacy': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 200
    assert 'Seleziona il tipo di partecipazione.' in resp.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0


def test_iscrizione_accompagnamento_compare_in_admin(client):
    data_corso_id = _crea_data_corso(
        'accompagnamento-nascita',
        'Corso di accompagnamento alla nascita',
        data='2099-07-18',
        ora='10:00',
    )
    token = _csrf_iscrizione(client, 'accompagnamento-nascita')

    resp = client.post('/iscrizione-corsi/accompagnamento-nascita', data={
        'nome': 'Luisa Verdi',
        'codice_fiscale': 'VRDLSU90A41G482Y',
        'telefono': '3331234567',
        'email': 'luisa@example.com',
        'data_nascita': '1990-01-01',
        'luogo_nascita': 'Pescara',
        'indirizzo': 'Via Roma 1',
        'citta': 'Montesilvano',
        'provincia': 'PE',
        'cap': '65015',
        'data_presunta_parto': '2026-12-01',
        'settimana_gravidanza': '20',
        'gravidanza_regolare': 'Si',
        'data_corso': data_corso_id,
        'consenso_privacy': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    csrf = _login_admin(client)
    admin_resp = client.get('/admin')
    assert 'Luisa Verdi' in admin_resp.text
    assert 'Corso di accompagnamento alla nascita' in admin_resp.text
    stato_resp = client.get(f'/admin/iscrizione-corso/1/Contattato?token={csrf}')
    assert stato_resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.first()
        assert iscrizione.stato == 'Contattato'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'open_day'


def test_iscrizione_senza_date_salva_richiesta_ricontatto(client):
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.data_corso == 'Da ricontattare per prossime date'
        assert iscrizione.corso_id is None
        assert iscrizione.tipo_richiesta == 'ricontatto'
        assert iscrizione.posti == 0
        assert iscrizione.extra_dict()['richiesta_prossime_date'] is True


def test_iscrizione_coppia_occupa_due_posti(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Coppia 60 euro',
        'data_corso': data_corso_id,
        'nome_secondo_partecipante': 'Luisa Verdi',
        'codice_fiscale_secondo_partecipante': 'VRDLSU90A41G482Y',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.posti == 2


def test_admin_mostra_panoramica_iscritti_per_corso(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    _login_admin(client)
    resp = client.get(f'/admin?corso_id={data_corso_id}')
    assert resp.status_code == 200
    assert 'Panoramica corsi e iscritti' in resp.text
    assert 'Disostruzione pediatrica' in resp.text
    assert 'posti stimati' in resp.text
    assert 'Richiesta iscrizione' in resp.text


def test_admin_filtra_iscritti_per_tipologia_corso(client):
    with flask_app.app_context():
        disostruzione = IscrizioneCorso(
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='2099-07-16',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
        )
        blsd = IscrizioneCorso(
            corso_tipo='bls-d',
            corso_titolo='BLSD',
            nome='Giulia Bianchi',
            telefono='3337654321',
            email='giulia@example.com',
            codice_fiscale='BNCGLI85A41G482Z',
            data_corso='2099-07-17',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
        )
        db.session.add_all([disostruzione, blsd])
        db.session.commit()

    _login_admin(client)
    resp = client.get('/admin?tipo_corso=disostruzione-pediatrica')
    assert resp.status_code == 200
    assert 'Visualizza iscritti per tipologia' in resp.text
    assert 'Disostruzione pediatrica' in resp.text
    assert 'Mario Rossi' in resp.text
    assert 'Giulia Bianchi' not in resp.text


def test_admin_aggiunge_iscritto_manualmente_e_crea_rubrica(client):
    data_corso_id = _crea_data_corso(
        'laboratorio-infanzia',
        "Laboratorio per l'infanzia",
        data='2099-07-20',
        ora='17:00',
    )
    csrf = _login_admin(client)

    resp = client.post('/admin/iscrizione-corso/aggiungi', data={
        'corso_id': data_corso_id,
        'nome': 'Anna Neri',
        'telefono': '3331234567',
        'email': 'anna@example.com',
        'codice_fiscale': '',
        'nome_bambino': 'Leo',
        'eta_bambino': '18 mesi',
        'tipo_richiesta': 'iscrizione_effettiva',
        'stato': 'Confermato',
        'posti': '1',
        'partecipazione': 'Bambino/a',
        'note': 'Prenotata da Instagram',
        'note_persona': 'Preferisce laboratorio pomeridiano',
        'consenso_privacy': 'on',
        '_csrf_token': csrf,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == f'/admin?corso_id={data_corso_id}#admin-corsi'
    with flask_app.app_context():
        persona = PersonaCorso.query.one()
        iscrizione = IscrizioneCorso.query.one()
        assert persona.nome == 'Anna Neri'
        assert persona.nome_bambino == 'Leo'
        assert persona.eta_bambino == '18 mesi'
        assert 'pomeridiano' in persona.note
        assert iscrizione.persona_id == persona.id
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.tipo_richiesta == 'iscrizione_effettiva'
        assert iscrizione.posti == 1
        assert iscrizione.codice_fiscale == ''
        assert iscrizione.extra_dict()['inserimento_admin'] is True


def test_admin_richiama_persona_da_rubrica_senza_duplicarla(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    with flask_app.app_context():
        persona = PersonaCorso(
            nome='Anna Neri',
            telefono='3331234567',
            email='anna@example.com',
            nome_bambino='Leo',
            eta_bambino='18 mesi',
        )
        db.session.add(persona)
        db.session.commit()
        persona_id = persona.id

    csrf = _login_admin(client)
    resp = client.post('/admin/iscrizione-corso/aggiungi', data={
        'corso_id': data_corso_id,
        'persona_id': str(persona_id),
        'tipo_richiesta': 'richiesta_iscrizione',
        'stato': 'Nuova',
        'posti': '1',
        'partecipazione': 'Iscrizione individuale',
        'consenso_privacy': 'on',
        '_csrf_token': csrf,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        assert PersonaCorso.query.count() == 1
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.persona_id == persona_id
        assert iscrizione.nome == 'Anna Neri'
        assert iscrizione.telefono == '3331234567'
        assert iscrizione.extra_dict()['nome_bambino'] == 'Leo'


def test_chiusure_studio_disabilitano_domeniche_festivi_e_sabato_pomeriggio(client):
    """Domeniche e festivi devono bloccare tutti gli orari; il sabato solo dopo le 11:30."""
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    resp_domenica = client.get(f'/api/orari-occupati/{domenica}')
    assert set(resp_domenica.get_json()) == set(app_module.ORARI_DISPONIBILI)

    resp_festivo = client.get('/api/orari-occupati/2099-12-25')
    assert set(resp_festivo.get_json()) == set(app_module.ORARI_DISPONIBILI)

    sabato = _prossimo_sabato_non_festivo().strftime('%Y-%m-%d')
    resp_sabato = client.get(f'/api/orari-occupati/{sabato}')
    orari_sabato = set(resp_sabato.get_json())
    assert '11:30' not in orari_sabato
    assert '12:00' in orari_sabato
    assert '12:30' in orari_sabato
    assert '15:00' in orari_sabato


def test_prenotazione_rifiutata_se_studio_chiuso(client):
    """Il server deve rifiutare una prenotazione inviata in un giorno di chiusura."""
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    token = _csrf_prenota(client)

    resp = client.post('/prenota', data={
        'nome': 'Mario Rossi', 'telefono': '333 1234567', 'email': 'mario@example.com',
        'servizio': 'Medicazione semplice', 'data': domenica, 'ora': '10:00',
        'consenso_privacy': 'on', '_csrf_token': token
    })

    assert 'studio è chiuso' in resp.text
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


def test_login_admin_ignora_redirect_esterno(client):
    """Il parametro next non deve poter portare l'admin verso domini esterni."""
    from werkzeug.security import generate_password_hash

    with flask_app.app_context():
        if not Admin.query.filter_by(username='admin').first():
            db.session.add(Admin(username='admin', password=generate_password_hash('cambiami123')))
            db.session.commit()

    token = _csrf_prenota(client)
    resp = client.post('/admin/login?next=https://example.com', data={
        'username': 'admin',
        'password': 'cambiami123',
        '_csrf_token': token
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/admin'


# ─── Integrazione Google Calendar (Arzamed) ───

@pytest.fixture
def calendario_finto(app):
    """Inietta un calendario Google finto (senza fare richieste di rete reali),
    con un appuntamento singolo e una chiusura settimanale ricorrente."""
    ics = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//IT
BEGIN:VEVENT
UID:appuntamento-arzamed-1@test
DTSTART;TZID=Europe/Rome:20260811T100000
DTEND;TZID=Europe/Rome:20260811T110000
SUMMARY:Visita paziente
END:VEVENT
BEGIN:VEVENT
UID:chiusura-ricorrente@test
DTSTART;TZID=Europe/Rome:20260803T150000
DTEND;TZID=Europe/Rome:20260803T160000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Chiuso
END:VEVENT
END:VCALENDAR
"""
    app_module.app.config['GOOGLE_CALENDAR_ICS_URL'] = 'https://esempio-fittizio.invalid/calendario.ics'
    app_module._cache_calendario['calendario'] = icalendar.Calendar.from_ical(ics)
    app_module._cache_calendario['scaricato_il'] = app_module.time.time()
    yield
    # Ripristina lo stato per non influenzare altri test
    app_module.app.config['GOOGLE_CALENDAR_ICS_URL'] = None
    app_module._cache_calendario['calendario'] = None
    app_module._cache_calendario['scaricato_il'] = 0


def test_calendario_google_blocca_appuntamento_singolo(calendario_finto):
    """Un appuntamento Arzamed (10:00-11:00) deve bloccare gli slot 10:00 e 10:30."""
    occupati = app_module.orari_occupati_da_calendario('2026-08-11')
    assert occupati == {'10:00', '10:30'}


def test_calendario_google_espande_ricorrenze(calendario_finto):
    """Una chiusura settimanale ricorrente deve applicarsi anche alle settimane successive."""
    occupati_originale = app_module.orari_occupati_da_calendario('2026-08-03')
    occupati_successivo = app_module.orari_occupati_da_calendario('2026-08-17')
    assert occupati_originale == {'15:00', '15:30'}
    assert occupati_successivo == {'15:00', '15:30'}


def test_calendario_google_nessun_evento(calendario_finto):
    """Un giorno senza eventi non deve risultare bloccato."""
    assert app_module.orari_occupati_da_calendario('2026-08-12') == set()


def test_endpoint_orari_occupati_unisce_db_e_calendario(client, calendario_finto):
    """L'endpoint /api/orari-occupati deve unire prenotazioni dal sito e impegni Arzamed."""
    with flask_app.app_context():
        appt = Appuntamento(
            nome='Prenotazione dal sito', telefono='333', email='sito@example.com',
            servizio='Test', data='2026-08-11', ora='16:00', stato='Confermato'
        )
        db.session.add(appt)
        db.session.commit()

    resp = client.get('/api/orari-occupati/2026-08-11')
    orari = set(resp.get_json())
    # 10:00/10:30 vengono da Arzamed (calendario), 16:00 dalla prenotazione sul sito
    assert orari == {'10:00', '10:30', '16:00'}


def test_prenotazione_rifiutata_se_occupata_su_calendario(client, calendario_finto):
    """Il server deve rifiutare una prenotazione per un orario già occupato su Arzamed,
    anche bypassando il controllo JavaScript lato client."""
    resp = client.get('/prenota')
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)

    resp = client.post('/prenota', data={
        'nome': 'Mario Rossi', 'telefono': '333 1234567', 'email': 'mario@example.com',
        'servizio': 'Medicazione semplice', 'data': '2026-08-11', 'ora': '10:00',
        'consenso_privacy': 'on', '_csrf_token': token
    })
    assert 'non è più disponibile' in resp.text
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


# ─── Scrittura su Google Calendar (conferma/spostamento/annullamento) ───

def _login_admin(client):
    """Helper: garantisce che esista un admin, effettua il login e restituisce
    un token CSRF valido per le azioni successive nell'area admin.

    Nota: il token CSRF usato per il login viene "consumato" (rimosso dalla
    sessione) dal server durante il controllo del login stesso, quindi non è
    riutilizzabile per le richieste successive: ne va letto uno nuovo dopo
    il login, ricaricando una pagina che lo rigeneri (es. /admin).
    """
    import re
    from werkzeug.security import generate_password_hash

    with flask_app.app_context():
        if not Admin.query.filter_by(username='admin').first():
            db.session.add(Admin(username='admin', password=generate_password_hash('cambiami123')))
            db.session.commit()

    resp = client.get('/admin/login')
    token_login = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)
    client.post('/admin/login', data={'username': 'admin', 'password': 'cambiami123', '_csrf_token': token_login})

    resp = client.get('/admin')
    with client.session_transaction() as sess:
        token_azioni = sess.get('_csrf_token')
    assert token_azioni, 'Login admin fallito: impossibile ottenere un token CSRF valido.'
    return token_azioni


def _csrf_admin(client):
    client.get('/admin')
    with client.session_transaction() as sess:
        token = sess.get('_csrf_token')
    assert token
    return token


def test_modulo_privato_accompagnamento_conferma_iscrizione_e_presenze(client):
    slug, percorso_id = _crea_percorso_accompagnamento()
    resp = client.get(f'/iscrizione-accompagnamento/{slug}')
    assert resp.status_code == 200
    assert 'infermiera, ostetrica, psicologa, osteopata e nutrizionista' in resp.text
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)

    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(f'/iscrizione-accompagnamento/{slug}', data={
            'nome': 'Luisa Verdi',
            'telefono': '3331234567',
            'email': 'luisa@example.com',
            'codice_fiscale': 'VRDLSU90A41G482Y',
            'data_presunta_parto': '2100-01-10',
            'partner_presente': 'Si',
            'consenso_privacy': 'on',
            'consenso_immagini': 'ACCONSENTO',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-accompagnamento/conferma'
    assert send_mock.call_count == 2
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        extra = iscrizione.extra_dict()
        assert iscrizione.percorso_accompagnamento_id == percorso_id
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.tipo_richiesta == 'iscrizione_effettiva'
        assert iscrizione.posti == 1
        assert iscrizione.partecipazione == 'Coppia - partner si'
        assert extra['data_presunta_parto'] == '2100-01-10'
        assert extra['partner_presente'] == 'Si'
        assert iscrizione.consenso_immagini is True
        assert PersonaCorso.query.count() == 1
        assert PresenzaAccompagnamento.query.count() == 9


def test_admin_gestisce_percorso_accompagnamento_e_export_pdf(client):
    csrf = _login_admin(client)
    resp = client.post('/admin/percorso-accompagnamento/aggiungi', data={
        'titolo': 'Iscrizione al corso',
        'slug': 'edizione-privata-test',
        'capienza_coppie': '6',
        'stato': 'Aperto',
        'contatti': '3806317175',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        percorso = PercorsoAccompagnamento.query.filter_by(slug='edizione-privata-test').one()
        percorso_id = percorso.id

    csrf = _csrf_admin(client)
    resp = client.post(f'/admin/percorso-accompagnamento/{percorso_id}/incontro/aggiungi', data={
        'numero': '1',
        'data': '2099-09-01',
        'ora': '17:00',
        'professionista': 'Ostetrica',
        'tema': 'Nascita e rientro a casa',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        percorso = db.session.get(PercorsoAccompagnamento, percorso_id)
        persona = PersonaCorso(nome='Luisa Verdi', telefono='3331234567', email='luisa@example.com')
        iscrizione = IscrizioneCorso(
            percorso_accompagnamento=percorso,
            persona=persona,
            corso_tipo='accompagnamento-nascita',
            corso_titolo=percorso.titolo,
            nome='Luisa Verdi',
            telefono='3331234567',
            email='luisa@example.com',
            codice_fiscale='VRDLSU90A41G482Y',
            data_corso='Percorso di 1 incontri',
            partecipazione='Coppia - partner si',
            dati_extra='{"data_presunta_parto": "2100-01-10", "partner_presente": "Si"}',
            tipo_richiesta='iscrizione_effettiva',
            posti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        db.session.add_all([persona, iscrizione])
        db.session.commit()
        iscrizione_id = iscrizione.id
        incontro_id = IncontroAccompagnamento.query.filter_by(percorso_id=percorso_id).one().id

    csrf = _csrf_admin(client)
    resp = client.post(f'/admin/percorso-accompagnamento/{percorso_id}/presenze', data={
        f'presenza_{iscrizione_id}_{incontro_id}': 'presente',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        presenza = PresenzaAccompagnamento.query.one()
        assert presenza.presente is True

    resp = client.get(f'/admin/percorso-accompagnamento/{percorso_id}/export-pdf')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert resp.data.startswith(b'%PDF')


@pytest.fixture
def google_calendar_scrittura_finto(app):
    """Configura la scrittura su Google Calendar e sostituisce il client API
    reale con un mock, per verificare le chiamate senza contattare Google."""
    app_module.app.config['GOOGLE_CALENDAR_ID'] = 'finto@group.calendar.google.com'
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = '/percorso/finto/service-account.json'
    mock_servizio = MagicMock()
    app_module._servizio_calendario_cache = mock_servizio
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._servizio_calendario_cache = None


def test_conferma_crea_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Confermare un appuntamento deve creare un evento su Google Calendar e
    salvarne l'ID sull'appuntamento."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events().insert().execute.return_value = {'id': 'evento-abc-123'}

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Lavaggio auricolare', data='2026-09-01', ora='10:00')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.get(f'/admin/aggiorna/{appt_id}/Confermato?token={csrf}')

    mock_servizio.events().insert.assert_called()
    corpo_inviato = mock_servizio.events().insert.call_args.kwargs['body']
    assert corpo_inviato['summary'] == 'Mario Rossi Lavaggio auricolare'

    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.google_event_id == 'evento-abc-123'


def test_annullamento_elimina_evento_da_calendario(client, google_calendar_scrittura_finto):
    """Annullare un appuntamento già confermato deve eliminare l'evento da
    Google Calendar e ripulire il riferimento salvato."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato', google_event_id='evento-da-eliminare')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.get(f'/admin/aggiorna/{appt_id}/Annullato?token={csrf}')

    mock_servizio.events().delete.assert_called_with(
        calendarId='finto@group.calendar.google.com', eventId='evento-da-eliminare'
    )
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.google_event_id is None


def test_spostamento_aggiorna_evento_esistente(client, google_calendar_scrittura_finto):
    """Spostare un appuntamento già collegato a un evento deve aggiornarlo
    (patch) invece di crearne uno nuovo."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato', google_event_id='evento-esistente')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.post(f'/admin/modifica/{appt_id}', data={
        'data': '2026-09-02', 'ora': '11:00', '_csrf_token': csrf
    })

    mock_servizio.events().patch.assert_called_once()
    kwargs = mock_servizio.events().patch.call_args.kwargs
    assert kwargs['eventId'] == 'evento-esistente'
    mock_servizio.events().insert.assert_not_called()


def test_aggiunta_corso_crea_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Creare un corso in admin deve creare anche l'evento Google Calendar."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {'id': 'evento-corso-123'}

    csrf = _login_admin(client)
    client.post('/admin/corso/aggiungi', data={
        'tipo': 'disostruzione-pediatrica',
        'titolo': 'Disostruzione pediatrica',
        'durata_ore': '2',
        'descrizione': 'Manovre salvavita per genitori e famiglie',
        'data': '2026-09-10',
        'ora': '18:00',
        'luogo': 'Studio infermieristico',
        '_csrf_token': csrf,
    })

    mock_servizio.events().insert.assert_called_once()
    kwargs = mock_servizio.events().insert.call_args.kwargs
    assert kwargs['calendarId'] == 'finto@group.calendar.google.com'
    assert kwargs['body']['summary'] == 'Corso: Disostruzione pediatrica'
    assert kwargs['body']['location'] == 'Studio infermieristico'
    assert kwargs['body']['start']['dateTime'].startswith('2026-09-10T18:00:00')
    assert kwargs['body']['end']['dateTime'].startswith('2026-09-10T20:00:00')

    with flask_app.app_context():
        corso = Corso.query.filter_by(titolo='Disostruzione pediatrica').one()
        assert corso.tipo == 'disostruzione-pediatrica'
        assert corso.durata_ore == 2
        assert corso.google_event_id == 'evento-corso-123'


def test_aggiunta_corso_usa_durata_modificata_su_calendario(client, google_calendar_scrittura_finto):
    """La durata modificabile nel form admin determina l'orario di fine su Calendar."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {'id': 'evento-blsd-123'}

    csrf = _login_admin(client)
    client.post('/admin/corso/aggiungi', data={
        'tipo': 'bls-d',
        'titolo': 'BLSD aziendale',
        'durata_ore': '4',
        'descrizione': 'Corso in azienda',
        'data': '2026-09-11',
        'ora': '09:00',
        'luogo': 'Azienda',
        '_csrf_token': csrf,
    })

    kwargs = mock_servizio.events().insert.call_args.kwargs
    assert kwargs['body']['start']['dateTime'].startswith('2026-09-11T09:00:00')
    assert kwargs['body']['end']['dateTime'].startswith('2026-09-11T13:00:00')

    with flask_app.app_context():
        corso = Corso.query.filter_by(titolo='BLSD aziendale').one()
        assert corso.tipo == 'bls-d'
        assert corso.durata_ore == 4


def test_eliminazione_corso_elimina_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Eliminare un corso in admin deve cancellare l'evento Google Calendar collegato."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        corso = Corso(
            titolo='Corso di accompagnamento alla nascita',
            tipo='accompagnamento-nascita',
            descrizione='Percorso in presenza',
            data='2026-09-12',
            ora='10:00',
            luogo='Studio',
            durata_ore=2,
            google_event_id='evento-corso-da-eliminare',
        )
        db.session.add(corso)
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    client.get(f'/admin/corso/elimina/{corso_id}?token={csrf}')

    mock_servizio.events().delete.assert_called_once_with(
        calendarId='finto@group.calendar.google.com',
        eventId='evento-corso-da-eliminare',
    )
    with flask_app.app_context():
        assert db.session.get(Corso, corso_id) is None


def test_spostamento_rifiuta_orario_non_prenotabile(client, google_calendar_scrittura_finto):
    """Anche l'area admin deve rispettare chiusure e orari prenotabili."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    resp = client.post(f'/admin/modifica/{appt_id}', data={
        'data': domenica, 'ora': '10:00', '_csrf_token': csrf
    })

    assert 'studio è chiuso' in resp.text
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.data == '2026-09-01'
        assert aggiornato.ora == '10:00'


def test_spostamento_rifiuta_slot_gia_occupato(client, google_calendar_scrittura_finto):
    """Spostare un appuntamento su uno slot già preso non deve sovrascrivere l'agenda."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato')
        occupato = Appuntamento(nome='Luisa Verdi', telefono='334', email='l@example.com',
                                servizio='Test', data='2026-09-02', ora='11:00',
                                stato='Confermato')
        db.session.add_all([appt, occupato])
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    resp = client.post(f'/admin/modifica/{appt_id}', data={
        'data': '2026-09-02', 'ora': '11:00', '_csrf_token': csrf
    })

    assert 'non è più disponibile' in resp.text
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.data == '2026-09-01'
        assert aggiornato.ora == '10:00'


def test_nessuna_chiamata_google_se_non_configurato(client):
    """Se la scrittura su Google Calendar non è configurata, confermare un
    appuntamento deve funzionare normalmente senza errori né chiamate API."""
    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    resp = client.get(f'/admin/aggiorna/{appt_id}/Confermato?token={csrf}', follow_redirects=True)
    assert resp.status_code == 200
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.stato == 'Confermato'
        assert aggiornato.google_event_id is None


def test_google_analytics_non_presente_se_non_configurato(client):
    flask_app.config['GOOGLE_ANALYTICS_ID'] = None

    resp = client.get('/')

    assert 'google-analytics-id' not in resp.text
    assert 'analytics-consent.js' not in resp.text
    assert 'Preferenze cookie' not in resp.text


def test_google_analytics_presente_se_configurato(client):
    flask_app.config['GOOGLE_ANALYTICS_ID'] = 'G-TEST1234'

    try:
        resp = client.get('/')
    finally:
        flask_app.config['GOOGLE_ANALYTICS_ID'] = None

    assert 'meta name="google-analytics-id" content="G-TEST1234"' in resp.text
    assert 'analytics-consent.js' in resp.text
    assert 'Preferenze cookie' in resp.text


if __name__ == '__main__':
    pytest.main([__file__])
