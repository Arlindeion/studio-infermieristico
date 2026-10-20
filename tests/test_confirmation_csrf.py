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
    assert app_module.db.session.get(app_module.IscrizioneCorso, registration.id).stato == 'Invitato'

    response = client.post(url, data={'_csrf_token': csrf})
    assert response.status_code == 200
    assert app_module.db.session.get(app_module.IscrizioneCorso, registration.id).stato == 'Nuova'
