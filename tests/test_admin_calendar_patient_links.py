import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import (
    Admin,
    AttivitaAdmin,
    CalendarPatientDecision,
    Persona,
    app as flask_app,
    db,
)
from config import config


@pytest.fixture
def app():
    flask_app.config.from_object(config['testing'])
    flask_app.config['GOOGLE_CALENDAR_ID'] = 'calendar-test'
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
    admin = Admin(
        username='calendar-patient-admin',
        password=generate_password_hash('password-test-calendar-patient-2026'),
    )
    db.session.add(admin)
    db.session.commit()
    with client.session_transaction() as browser_session:
        browser_session['_csrf_token'] = 'login-token'
    response = client.post('/admin/login', data={
        '_csrf_token': 'login-token',
        'username': 'calendar-patient-admin',
        'password': 'password-test-calendar-patient-2026',
    })
    assert response.status_code == 302
    return admin


def _csrf(client, token='calendar-decision-token'):
    with client.session_transaction() as browser_session:
        browser_session['_csrf_token'] = token
    return token


def _patient(first_name='Mario', last_name='Rossi', state='attiva'):
    patient = Persona(
        nome=first_name,
        cognome=last_name,
        stato=state,
        archiviato_il=(datetime.now(timezone.utc) if state == 'archiviata' else None),
    )
    db.session.add(patient)
    db.session.commit()
    return patient


def _calendar_event(
    event_id='calendar-1',
    summary='Rossi Mario · Medicazione',
    start='2025-09-11T10:00:00+02:00',
    description='Dato sanitario da non mostrare',
    private_properties=None,
):
    event = {
        'id': event_id,
        'status': 'confirmed',
        'summary': summary,
        'description': description,
        'start': {'dateTime': start, 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': start.replace('10:00:00', '10:30:00'), 'timeZone': 'Europe/Rome'},
    }
    if private_properties:
        event['extendedProperties'] = {'private': private_properties}
    return event


def test_patient_calendar_history_is_lazy_and_unavailable_state_is_visible(client):
    _login(client)
    patient = _patient()

    with patch.object(app_module, '_calendar_patient_history') as history:
        response = client.get(f'/admin/paziente/{patient.id}')
    assert response.status_code == 200
    history.assert_not_called()
    assert 'Cerca eventi su Calendar' in response.text

    with patch.object(app_module, '_ottieni_servizio_calendario', return_value=None):
        response = client.get(f'/admin/paziente/{patient.id}?calendar=1')
    assert response.status_code == 200
    assert 'Google Calendar non è disponibile' in response.text
    assert 'Nessuna nuova possibile corrispondenza' not in response.text


def test_candidate_is_not_linked_automatically_and_hides_description(client):
    _login(client)
    patient = _patient()
    event = _calendar_event()

    with (
        patch.object(app_module, '_calendar_list_all_events', return_value=([event], False)),
        patch.object(app_module, '_calendar_read_service', return_value=('calendar-test', object())),
    ):
        response = client.get(f'/admin/paziente/{patient.id}?calendar=1')

    assert response.status_code == 200
    assert 'Possibili corrispondenze' in response.text
    assert 'Rossi Mario · Medicazione' in response.text
    assert 'Dato sanitario da non mostrare' not in response.text
    assert CalendarPatientDecision.query.count() == 0


def test_manual_link_and_rejection_are_persisted_and_audited(client):
    admin = _login(client)
    patient = _patient()
    event = _calendar_event()

    token = _csrf(client)
    with patch.object(app_module, '_calendar_get_event', return_value=event):
        response = client.post(
            f'/admin/paziente/{patient.id}/calendar-decision',
            data={
                '_csrf_token': token,
                'google_event_id': event['id'],
                'action': 'link',
            },
        )
    assert response.status_code == 302
    decision = CalendarPatientDecision.query.one()
    assert decision.decision == 'linked'
    assert decision.admin_id == admin.id

    token = _csrf(client, 'calendar-reject-token')
    with patch.object(app_module, '_calendar_get_event', return_value=event):
        response = client.post(
            f'/admin/paziente/{patient.id}/calendar-decision',
            data={
                '_csrf_token': token,
                'google_event_id': event['id'],
                'action': 'reject',
            },
        )
    assert response.status_code == 302
    db.session.refresh(decision)
    assert decision.decision == 'rejected'
    assert decision.admin_id == admin.id


def test_manual_link_can_be_removed_without_reading_calendar(client):
    admin = _login(client)
    patient = _patient()
    decision = CalendarPatientDecision(
        persona_id=patient.id,
        google_event_id='calendar-linked-1',
        decision='linked',
        admin_id=admin.id,
    )
    db.session.add(decision)
    db.session.commit()

    token = _csrf(client)
    with patch.object(app_module, '_calendar_get_event') as calendar_reader:
        response = client.post(
            f'/admin/paziente/{patient.id}/calendar-decision',
            data={
                '_csrf_token': token,
                'google_event_id': decision.google_event_id,
                'action': 'unlink',
            },
        )

    assert response.status_code == 302
    calendar_reader.assert_not_called()
    assert CalendarPatientDecision.query.count() == 0


def test_linked_event_cannot_be_linked_to_a_second_patient(client):
    admin = _login(client)
    first_patient = _patient('Mario', 'Rossi')
    second_patient = _patient('Mario', 'Rossi')
    event = _calendar_event()
    db.session.add(CalendarPatientDecision(
        persona_id=first_patient.id,
        google_event_id=event['id'],
        decision='linked',
        admin_id=admin.id,
    ))
    db.session.commit()

    token = _csrf(client)
    with patch.object(app_module, '_calendar_get_event', return_value=event):
        response = client.post(
            f'/admin/paziente/{second_patient.id}/calendar-decision',
            data={
                '_csrf_token': token,
                'google_event_id': event['id'],
                'action': 'link',
            },
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert 'già collegato a un’altra anagrafica' in response.text
    assert CalendarPatientDecision.query.filter_by(decision='linked').count() == 1


def test_archived_patient_cannot_change_calendar_decisions(client):
    _login(client)
    patient = _patient(state='archiviata')
    token = _csrf(client)
    response = client.post(
        f'/admin/paziente/{patient.id}/calendar-decision',
        data={
            '_csrf_token': token,
            'google_event_id': 'calendar-1',
            'action': 'link',
        },
    )
    assert response.status_code == 404


def test_site_owned_orphan_is_excluded_and_queued_once(app):
    event = _calendar_event(
        event_id='site-orphan-1',
        private_properties={
            'studioSource': 'sito-admin',
            'studioEntity': 'Appuntamento',
            'studioEntityId': '999',
        },
    )
    assert app_module._queue_orphan_site_calendar_events([event], set()) == 1
    assert app_module._queue_orphan_site_calendar_events([event], set()) == 0
    assert AttivitaAdmin.query.filter_by(stato='Aperta').count() == 1


def test_rejected_and_site_owned_events_are_not_patient_candidates(app):
    patient = _patient()
    rejected = _calendar_event(event_id='rejected-1')
    site_owned = _calendar_event(
        event_id='site-owned-1',
        private_properties={
            'studioSource': 'sito-admin',
            'studioEntity': 'Appuntamento',
            'studioEntityId': '77',
        },
    )
    db.session.add(CalendarPatientDecision(
        persona_id=patient.id,
        google_event_id='rejected-1',
        decision='rejected',
    ))
    db.session.commit()

    with flask_app.test_request_context('/admin/paziente/1?calendar=1'):
        with (
            patch.object(
                app_module,
                '_calendar_list_all_events',
                return_value=([rejected, site_owned], False),
            ),
            patch.object(app_module, '_calendar_read_service', return_value=('calendar-test', object())),
        ):
            state = app_module._calendar_patient_history(patient, 1)

    assert state['candidate_total'] == 0
    assert AttivitaAdmin.query.filter_by(stato='Aperta').count() == 1


def test_calendar_reader_marks_an_interrupted_later_page_as_partial(app):
    service = MagicMock()
    with (
        patch.object(app_module, '_calendar_read_service', return_value=('calendar-test', service)),
        patch.object(
            app_module,
            '_esegui_richiesta_calendario',
            side_effect=[
                {'items': [_calendar_event()], 'nextPageToken': 'page-2'},
                RuntimeError('calendar unavailable'),
            ],
        ),
    ):
        events, partial = app_module._calendar_list_all_events('Rossi')

    assert [event['id'] for event in events] == ['calendar-1']
    assert partial is True
    second_call = service.events.return_value.list.call_args_list[1]
    assert second_call.kwargs['pageToken'] == 'page-2'


def test_global_search_sends_the_exact_query_but_never_renders_description(client):
    _login(client)
    event = _calendar_event(summary='Evento trovato')
    query = 'RSSMRA80A01H501U'

    with (
        patch.object(app_module, '_riconciliazione_admin_se_necessaria', return_value=None),
        patch.object(app_module, '_agenda_operativa', return_value=[]),
        patch.object(app_module, '_calendar_list_all_events', return_value=([event], False)) as reader,
    ):
        response = client.get(f'/admin?q={query}')

    assert response.status_code == 200
    reader.assert_called_once_with(query)
    assert 'Evento trovato' in response.text
    assert 'Dato sanitario da non mostrare' not in response.text
    assert 'inviato anche a Google Calendar' in response.text


def test_patient_candidates_are_recent_first_and_paginated(app):
    patient = _patient()
    events = [
        _calendar_event(
            event_id=f'event-{index:02d}',
            start=f'2025-09-{index + 1:02d}T10:00:00+02:00',
        )
        for index in range(21)
    ]
    with app.test_request_context('/admin/paziente/1?calendar=1'):
        with (
            patch.object(app_module, '_calendar_list_all_events', return_value=(events, False)),
            patch.object(app_module, '_calendar_read_service', return_value=('calendar-test', object())),
        ):
            first_page = app_module._calendar_patient_history(patient, 1)
            second_page = app_module._calendar_patient_history(patient, 2)

    assert first_page['candidate_total'] == 21
    assert first_page['pages'] == 2
    assert first_page['candidates'][0]['id'] == 'event-20'
    assert second_page['candidates'][0]['id'] == 'event-00'
