import os
import sys
import pytest
import icalendar
from datetime import date, datetime

# Assicurarsi che l'applicazione possa essere importata
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import app as flask_app
from config import config
from app import db, Appuntamento, Admin, Corso

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
        print('Dopo la cancellazione, orari occupati:', data2)  # DEBUG
        assert '10:30' not in data2  # dovrebbe essere libero dopo la cancellazione

def test_holiday_flow(client):
    """Semplice test della home page."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'S.C. Studio Infermieristico' in resp.data  # adeguare in base al contenuto effettivo


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


if __name__ == '__main__':
    pytest.main([__file__])