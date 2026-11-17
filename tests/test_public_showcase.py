"""Brochure mode blocks public mutations while preserving contact requests."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

import app as module
from tests.test_app import app, client


@pytest.fixture(autouse=True)
def showcase(app):
    app.config['PUBLIC_SITE_MODE'] = 'showcase'
    app.config['MAIL_ADMIN_RECIPIENT'] = 'studio@example.invalid'
    yield
    app.config['PUBLIC_SITE_MODE'] = 'full'


def token(client):
    with client.session_transaction() as session:
        session['_csrf_token'] = 'showcase-test-token'
    return 'showcase-test-token'


@pytest.mark.parametrize('path', [
    '/api/orari-occupati/2026-12-01', '/api/orari-call-sonno/2026-12-01',
    '/offerta-sonno/' + 'x' * 40, '/questionario-sonno/' + 'x' * 40,
    '/proposta-slot/' + 'x' * 40, '/lista-attesa/' + 'x' * 40,
])
def test_old_links_and_availability_are_disabled(client, path):
    with patch.object(module, '_ottieni_servizio_calendario') as calendar:
        assert client.get(path).status_code == 503
        assert client.post(path, data={}).status_code in {405, 503}
        calendar.assert_not_called()
    assert module.Appuntamento.query.count() == 0
    assert module.CallSonno.query.count() == 0


@pytest.mark.parametrize('path', ['/prenota', '/prenota-call-sonno', '/iscrizione-accompagnamento/private'])
def test_stale_booking_form_cannot_create_an_appointment(client, path):
    assert client.get(path).status_code == 303
    assert client.post(path, data={'_csrf_token': token(client)}).status_code == 503
    assert module.Appuntamento.query.count() == 0
    assert module.CallSonno.query.count() == 0


def test_open_course_still_only_accepts_interest(client):
    course = module.Corso(tipo='disostruzione-pediatrica', titolo='Corso prova',
                          data=(date.today() + timedelta(days=30)).isoformat(),
                          ora='10:00', stato='Aperto', capienza_massima=10)
    module.db.session.add(course)
    module.db.session.commit()
    html = client.get('/iscrizione-corsi/disostruzione-pediatrica').get_data(as_text=True)
    assert 'name="data_corso"' not in html
    assert 'name="codice_fiscale"' not in html
    assert 'course-interest-form' in html
    response = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        '_csrf_token': token(client), 'nome': 'Persona Prova', 'telefono': '3331234567',
        'email': 'prova@example.invalid', 'consenso_privacy': 'on', 'data_corso': str(course.id),
    })
    assert response.status_code == 302
    interest = module.IscrizioneCorso.query.one()
    assert interest.tipo_richiesta == 'ricontatto'
    assert interest.corso_id is None
    assert interest.posti == 0


@pytest.mark.parametrize('kind', ['prestazioni', 'sonno'])
@pytest.mark.parametrize('smtp_failure', [False, True])
def test_interest_is_durable_and_only_emails_the_studio(client, kind, smtp_failure):
    with patch.object(module.mail, 'send', side_effect=RuntimeError('SMTP') if smtp_failure else None) as send:
        response = client.post('/interesse/' + kind, data={
            '_csrf_token': token(client), 'nome': 'Persona Prova', 'telefono': '3331234567',
            'email': 'prova@example.invalid', 'consenso_privacy': 'on',
            'note': 'ignored', 'data': '2026-12-01',
        })
    assert response.status_code == 303
    record = module.EmailOperativa.query.one()
    assert record.entita_tipo == 'InteresseVetrina'
    assert record.stato == ('fallita' if smtp_failure else 'soppressa')
    assert 'ignored' not in record.corpo
    assert send.call_args.args[0].recipients == ['studio@example.invalid']
    assert module.Appuntamento.query.count() == module.CallSonno.query.count() == 0
    if smtp_failure:
        assert module.RegistroEvento.query.filter_by(esito='errore').count() == 1


def test_interest_requires_csrf_and_valid_contact(client):
    assert client.post('/interesse/prestazioni', data={}).status_code == 400
    assert client.post('/interesse/prestazioni', data={'_csrf_token': token(client)}).status_code == 400
    assert module.EmailOperativa.query.count() == 0


@pytest.mark.parametrize('path', ['/', '/iscrizione-corsi', '/iscrizione-corsi/blsd',
                                '/iscrizione-corsi/disostruzione-pediatrica',
                                '/iscrizione-corsi/accompagnamento-nascita',
                                '/iscrizione-corsi/laboratorio-infanzia',
                                '/prestazioni-infermieristiche', '/consulenze-online'])
def test_public_pages_render_without_booking_controls(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('<h1') == 1
    assert 'href="/prenota"' not in html
    assert 'href="/prenota-call-sonno"' not in html
    assert 'name="data_corso"' not in html
    assert 'no-store' in response.headers['Cache-Control']


def test_full_version_remains_available_and_admin_stays_protected(client, app):
    assert client.get('/admin').status_code == 302
    app.config['PUBLIC_SITE_MODE'] = 'full'
    assert client.get('/prenota').status_code == 200
    assert client.post('/interesse/prestazioni').status_code == 404
