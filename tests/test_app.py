import os
import sys
import pytest
from datetime import date, datetime

# Assicurarsi che l'applicazione possa essere importata
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

if __name__ == '__main__':
    pytest.main([__file__])