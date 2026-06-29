import os
import sys
import pytest
from datetime import date, datetime

# Ensure the application can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app
from config import config
from app import db, Appuntamento, Admin, Corso

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Use testing configuration
    flask_app.config.from_object(config['testing'])
    # Establish an application context
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

def test_app_exists(app):
    """Sanity check that the app exists."""
    assert app is not None

def test_app_is_testing(app):
    """Ensure the app is in testing mode."""
    assert app.config['TESTING'] == True

def test_database_empty(app):
    """Start with a blank database."""
    with app.app_context():
        assert Appuntamento.query.count() == 0
        assert Admin.query.count() == 0
        assert Corso.query.count() == 0

def test_create_admin(app):
    """Test that an admin can be created."""
    with app.app_context():
        admin = Admin(username='testadmin', password='hashed')
        db.session.add(admin)
        db.session.commit()
        assert Admin.query.filter_by(username='testadmin').first() is not None

def test_create_appointment(app):
    """Test creating an appointment."""
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
        assert saved.stato == 'In attesa'  # default

def test_orari_occupati_endpoint(client):
    """Test the /api/orari-occupati/<data> endpoint."""
    with flask_app.app_context():
        # Insert an appointment for a specific date
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
        # Request the endpoint
        resp = client.get('/api/orari-occupati/2026-07-10')
        assert resp.status_code == 200
        data = resp.get_json()
        assert '10:30' in data
        # Ensure cancelled appointments are not included
        appt.stato = 'Annullato'
        db.session.commit()
        resp2 = client.get('/api/orari-occupati/2026-07-10')
        data2 = resp2.get_json()
        print('After cancellation, occupied times:', data2)  # DEBUG
        assert '10:30' not in data2  # should be free after cancellation

def test_holiday_flow(client):
    """Simple test of the home page."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'S.C. Studio Infermieristico' in resp.data  # adjust based on actual content

if __name__ == '__main__':
    pytest.main([__file__])