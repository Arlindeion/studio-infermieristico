"""Regression gates for patient-facing CSRF-protected confirmation pages."""

import re
from datetime import datetime
from types import SimpleNamespace

import pytest

import app as app_module
from config import config


@pytest.fixture
def client():
    flask_app = app_module.app
    flask_app.config.from_object(config['testing'])
    with flask_app.app_context():
        app_module.db.create_all()
        app_module._azzera_stato_calendario()
        yield flask_app.test_client()
        app_module._azzera_stato_calendario()
        app_module.db.session.remove()
        app_module.db.drop_all()


def _form_csrf_token(response):
    match = re.search(r'name="_csrf_token" value="([^"]+)"', response.text)
    assert match, 'Confirmation form is missing the anti-CSRF token.'
    return match.group(1)


def test_proposed_slot_rejects_csrf_before_updating_state(client, monkeypatch):
    proposal = app_module.PropostaSlot(
        token='synthetic-proposal-token',
        entita_tipo='Appuntamento',
        entita_id=987,
        data_proposta='2099-01-02',
        ora_proposta='10:00',
        durata_minuti=30,
        stato='Inviata',
        scade_il=datetime(2099, 1, 3),
    )
    app_module.db.session.add(proposal)
    app_module.db.session.commit()
    monkeypatch.setattr(
        app_module, '_entita_admin',
        lambda *_: SimpleNamespace(id=987, google_event_id=None),
    )
    monkeypatch.setattr(app_module, 'slot_occupato_db', lambda *a, **kw: True)

    url = '/proposta-slot/synthetic-proposal-token'
    page = client.get(url)
    assert page.status_code == 200
    csrf = _form_csrf_token(page)

    assert client.post(url).status_code == 400
    assert client.post(url, data={'_csrf_token': 'bad'}).status_code == 400
    assert client.post(url, data={'_csrf_token': 'è'}).status_code == 400
    assert app_module.db.session.get(app_module.PropostaSlot, proposal.id).stato == 'Inviata'

    response = client.post(url, data={'_csrf_token': csrf})
    assert response.status_code == 200
    assert app_module.db.session.get(app_module.PropostaSlot, proposal.id).stato == 'Non disponibile'


def test_waitlist_rejects_csrf_before_updating_state(client, monkeypatch):
    course = app_module.Corso(titolo='Corso sintetico', data='2099-01-02')
    registration = app_module.IscrizioneCorso(
        corso=course,
        corso_tipo='disostruzione-pediatrica',
        corso_titolo='Corso sintetico',
        nome='Partecipante sintetico',
        telefono='3330000000',
        codice_fiscale='TEST-ONLY',
        stato='Invitato',
        data_corso='2099-01-02',
        token_lista_attesa='synthetic-waitlist-token',
        scadenza_invito_lista_attesa=datetime(2099, 1, 3),
        posti_richiesti=1,
    )
    app_module.db.session.add(registration)
    app_module.db.session.commit()
    monkeypatch.setattr(app_module, '_corso_accetta_prenotazione_online', lambda *a, **kw: True)
    monkeypatch.setattr(app_module, 'invia_email_alert_nuova_iscrizione', lambda *_: None)

    url = '/lista-attesa/synthetic-waitlist-token'
    page = client.get(url)
    assert page.status_code == 200
    csrf = _form_csrf_token(page)

    assert client.post(url).status_code == 400
    assert client.post(url, data={'_csrf_token': 'bad'}).status_code == 400
    assert client.post(url, data={'_csrf_token': 'è'}).status_code == 400
    assert app_module.db.session.get(app_module.IscrizioneCorso, registration.id).stato == 'Invitato'

    response = client.post(url, data={'_csrf_token': csrf})
    assert response.status_code == 200
    assert app_module.db.session.get(app_module.IscrizioneCorso, registration.id).stato == 'Nuova'


@pytest.mark.parametrize('invalid_date', ['2026-02-30', '2026-13-01', 'not-a-date'])
def test_call_availability_rejects_invalid_dates(client, invalid_date):
    assert client.get(f'/api/orari-call-sonno/{invalid_date}').status_code == 400


def test_edit_availability_excludes_only_own_record_and_calendar_event(client, monkeypatch):
    appointment = app_module.Appuntamento(
        nome='Persona sintetica', telefono='3330000000', email='test@example.invalid',
        servizio='Prestazione sintetica', data='2099-08-11', ora='10:00',
        google_event_id='synthetic-own-event',
    )
    administrator = app_module.Admin(
        username='synthetic_admin',
        password=app_module.generate_password_hash('synthetic-password-only'),
    )
    app_module.db.session.add_all([appointment, administrator])
    app_module.db.session.commit()
    start, end = app_module._intervallo_locale('2099-08-11', '10:00', 30)
    events = [(start, end, 'synthetic-own-event'), (start, end, 'synthetic-other-event')]
    monkeypatch.setattr(app_module, '_scarica_intervalli_calendario', lambda *_: events)
    url = f'/api/orari-occupati/2099-08-11?ignore_id={appointment.id}'

    # Public callers cannot hide a saved appointment by supplying its ID.
    assert '10:00' in client.get(url).get_json()
    login_page = client.get('/admin/login')
    login = client.post('/admin/login', data={
        '_csrf_token': _form_csrf_token(login_page),
        'username': 'synthetic_admin', 'password': 'synthetic-password-only',
    })
    assert login.status_code == 302
    assert '10:00' in client.get(url).get_json()
    events.pop()
    assert '10:00' not in client.get(url).get_json()

    app_module.db.session.add(app_module.BloccoAgenda(
        titolo='Pausa sintetica', data='2099-08-11', ora='10:00', durata_minuti=30,
    ))
    app_module.db.session.commit()
    assert '10:00' in client.get(url).get_json()
