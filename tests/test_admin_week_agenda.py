import os
import sys
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import Admin, Appuntamento, app as flask_app, db
from config import config


@pytest.fixture
def app():
    flask_app.config.from_object(config['testing'])
    with flask_app.app_context():
        db.create_all()
        app_module._azzera_stato_calendario()
        yield flask_app
        app_module._azzera_stato_calendario()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    db.session.add(Admin(
        username='agenda-admin',
        password=generate_password_hash('password-test-agenda-2026'),
    ))
    db.session.commit()
    with client.session_transaction() as session:
        session['_csrf_token'] = 'login-token'
    response = client.post('/admin/login', data={
        '_csrf_token': 'login-token',
        'username': 'agenda-admin',
        'password': 'password-test-agenda-2026',
    })
    assert response.status_code == 302


def _csrf(client, token='agenda-csrf'):
    with client.session_transaction() as session:
        session['_csrf_token'] = token
    return token


def test_admin_senza_parametri_apre_la_settimana(client):
    _login(client)
    with patch.object(app_module, '_riconciliazione_admin_se_necessaria', return_value=None):
        response = client.get('/admin')
    assert response.status_code == 200
    assert 'data-admin-week-grid' in response.text
    assert 'Conferma e manda mail al paziente' in response.text


def test_evento_calendar_esterno_e_posizionato_lato_server_nella_fascia_oraria(client):
    _login(client)
    evento_esterno = {
        'tipo': 'Esterno',
        'id': 'calendar-esterno-17',
        'titolo': 'Visita da Calendar',
        'inizio': datetime(2026, 9, 7, 17, 0),
        'fine': datetime(2026, 9, 7, 17, 30),
        'stato': 'Calendar / Arzamed',
        'sincronizzazione': 'esterno',
        'url': None,
        'dettagli': [],
        'note': None,
        'ha_email': False,
        'spostabile_calendar': True,
    }

    with (
        patch.object(
            app_module,
            '_riconciliazione_admin_se_necessaria',
            return_value=None,
        ),
        patch.object(
            app_module,
            '_agenda_operativa',
            return_value=[evento_esterno],
        ),
    ):
        response = client.get('/admin?vista=settimana&data=2026-09-07')

    assert response.status_code == 200
    assert 'data-event-start="17:00"' in response.text
    assert (
        'style="top: 66.666667%; height: 3.333333%;"'
        in response.text
    )


def test_drag_evento_calendar_esterno_aggiorna_google_senza_mail(app, client):
    _login(client)
    token = _csrf(client)
    app.config['GOOGLE_CALENDAR_ID'] = 'calendar-test'
    servizio = MagicMock()
    remoto = {
        'id': 'evento-esterno-1',
        'status': 'confirmed',
        'summary': 'Mario Rossi Medicazione semplice',
        'start': {
            'dateTime': '2026-09-11T10:00:00+02:00',
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': '2026-09-11T10:30:00+02:00',
            'timeZone': 'Europe/Rome',
        },
    }
    aggiornato = {
        **remoto,
        'start': {
            'dateTime': '2026-09-11T11:00:00+02:00',
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': '2026-09-11T11:30:00+02:00',
            'timeZone': 'Europe/Rome',
        },
    }

    with (
        patch.object(app_module, 'local_today', return_value=date(2026, 9, 10)),
        patch.object(app_module, '_ottieni_servizio_calendario', return_value=servizio),
        patch.object(
            app_module,
            '_esegui_richiesta_calendario',
            side_effect=[remoto, aggiornato],
        ),
        patch.object(app_module, 'slot_occupato_db', return_value=False),
        patch.object(app_module, 'intervallo_occupato_da_calendario', return_value=False),
        patch.object(app_module, '_invalida_cache_calendario') as invalida_cache,
    ):
        response = client.post(
            '/admin/calendar-esterno/sposta-agenda',
            data={
                '_csrf_token': token,
                'event_id': 'evento-esterno-1',
                'data_originale': '2026-09-11',
                'ora_originale': '10:00',
                'fine_originale': '10:30',
                'data': '2026-09-11',
                'ora': '11:00',
                'invia_email': '0',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True
    assert payload['calendar_ok'] is True
    assert payload['email_sent'] is None
    kwargs_patch = servizio.events.return_value.patch.call_args.kwargs
    assert kwargs_patch['eventId'] == 'evento-esterno-1'
    assert kwargs_patch['sendUpdates'] == 'none'
    assert kwargs_patch['body']['start']['dateTime'].startswith(
        '2026-09-11T11:00:00'
    )
    invalida_cache.assert_called_once()


@pytest.mark.parametrize(('mail_choice', 'mail_expected'), [('0', False), ('1', True)])
def test_drag_sposta_e_invia_mail_solo_se_richiesto(app, client, mail_choice, mail_expected):
    _login(client)
    appointment = Appuntamento(
        nome='Mario Rossi',
        telefono='3331234567',
        email='mario@example.com',
        servizio='Controllo parametri vitali',
        data='2026-09-11',
        ora='10:00',
        duration_minutes=30,
        stato='Confermato',
        sincronizzazione='sincronizzato',
        consenso_privacy=True,
    )
    db.session.add(appointment)
    db.session.commit()
    appointment_id = appointment.id
    token = _csrf(client)

    with (
        patch.object(app_module, 'local_today', return_value=date(2026, 9, 10)),
        patch.object(app_module, 'is_appointment_interval_bookable', return_value=True),
        patch.object(app_module, 'slot_occupato_db', return_value=False),
        patch.object(app_module, 'intervallo_occupato_da_calendario', return_value=False),
        patch.object(app_module, 'crea_o_aggiorna_evento_calendario', return_value=True) as calendar_mock,
        patch.object(app_module, 'invia_email_spostamento', return_value=True) as mail_mock,
    ):
        response = client.post(
            f'/admin/appuntamento/{appointment_id}/sposta-agenda',
            data={
                '_csrf_token': token,
                'data_originale': '2026-09-11',
                'ora_originale': '10:00',
                'data': '2026-09-11',
                'ora': '11:00',
                'invia_email': mail_choice,
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )

    assert response.status_code == 200
    assert response.get_json()['ok'] is True
    moved = db.session.get(Appuntamento, appointment_id)
    assert moved.ora == '11:00'
    calendar_mock.assert_called_once()
    if mail_expected:
        mail_mock.assert_called_once()
    else:
        mail_mock.assert_not_called()


def test_drag_rifiuta_una_pagina_stale_senza_modificare_il_dato(app, client):
    _login(client)
    appointment = Appuntamento(
        nome='Mario Rossi',
        telefono='3331234567',
        email='mario@example.com',
        servizio='Controllo parametri vitali',
        data='2026-09-11',
        ora='10:30',
        duration_minutes=30,
        stato='Confermato',
        sincronizzazione='sincronizzato',
        consenso_privacy=True,
    )
    db.session.add(appointment)
    db.session.commit()
    appointment_id = appointment.id
    token = _csrf(client)

    response = client.post(
        f'/admin/appuntamento/{appointment_id}/sposta-agenda',
        data={
            '_csrf_token': token,
            'data_originale': '2026-09-11',
            'ora_originale': '10:00',
            'data': '2026-09-11',
            'ora': '11:00',
            'invia_email': '1',
        },
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )

    assert response.status_code == 409
    assert db.session.get(Appuntamento, appointment_id).ora == '10:30'
