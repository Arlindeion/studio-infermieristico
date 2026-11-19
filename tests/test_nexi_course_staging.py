"""Explicit remote course sandbox; no real gateway, email, Calendar or database."""
import base64
from unittest.mock import Mock

import pytest

import app as site
from tests.test_nexi_course_sandbox import (
    application, client, course, gateway, csrf, enroll, attempt, operation, notify,
    BASE, COURSE_URL, SECURITY_TOKEN,
)


@pytest.fixture(autouse=True)
def remote_mode(application, monkeypatch):
    for key, value in {
        'APP_ENV': 'staging', 'NEXI_SANDBOX_ENABLED': False,
        'NEXI_SANDBOX_ISOLATED': False,
        'NEXI_COURSE_SANDBOX_ENABLED': True,
        'NEXI_COURSE_SANDBOX_API_KEY': 'synthetic-staging-key',
        'STAGING_AUTH_USERNAME': 'synthetic-tester',
        'STAGING_AUTH_PASSWORD': 'synthetic-staging-password',
    }.items():
        monkeypatch.setitem(application.config, key, value)


@pytest.fixture
def authenticated_client(client):
    token = base64.b64encode(b'synthetic-tester:synthetic-staging-password').decode()
    client.environ_base['HTTP_AUTHORIZATION'] = 'Basic ' + token
    return client


@pytest.mark.parametrize('participation,deposit', [('Singolo 34 euro', 1700), ('Coppia 60 euro', 3000)])
def test_remote_course_deposit_and_notification_keep_browser_auth(application, authenticated_client,
                                                                 course, gateway, participation, deposit):
    page = authenticated_client.get(COURSE_URL)
    assert page.status_code == 200
    assert 'Paga l’acconto del 50%' in page.text
    assert 'Nessun addebito reale' in page.text
    enroll(authenticated_client, course, partecipazione=participation,
           nome_secondo_partecipante='Secondo partecipante di prova')
    payment = attempt()
    assert payment.amount_cents == deposit
    gateway[1].return_value = {'operations': [operation(payment)]}
    unauthenticated = application.test_client()
    assert unauthenticated.get(COURSE_URL).status_code == 401
    result_path = BASE + '/result/' + payment.access_token
    assert unauthenticated.get(result_path).status_code == 401
    assert unauthenticated.post(result_path+'/retry', data={}).status_code == 401
    assert notify(unauthenticated, payment, securityToken='synthetic-forged-token').status_code == 403
    assert notify(unauthenticated, payment).status_code == 200
    assert payment.registration.stato == 'Confermato'
    assert payment.registration.persona_v2_id is not None
    message = site.EmailOperativa.query.filter_by(entita_tipo='IscrizioneCorso').one()
    assert message.oggetto.startswith('[PROVA NEXI] Posto confermato -')
    assert 'nessun addebito reale' in message.corpo
    assert authenticated_client.get(result_path).status_code == 200
    assert authenticated_client.get('/payments/nexi/sandbox/result/'+'a'*64).status_code == 404


@pytest.mark.parametrize('key,value', [
    ('NEXI_COURSE_SANDBOX_ENABLED', False), ('NEXI_COURSE_SANDBOX_API_KEY', None),
    ('PUBLIC_BASE_URL', 'http://localhost'), ('STAGING_AUTH_USERNAME', None),
    ('STAGING_AUTH_PASSWORD', None),
])
def test_remote_mode_requires_every_explicit_setting(application, authenticated_client, course, gateway,
                                                     monkeypatch, key, value):
    from course_payment_sandbox import course_sandbox_ready
    monkeypatch.setitem(application.config, key, value)
    assert course_sandbox_ready() is False
    gateway[0].assert_not_called()


@pytest.mark.parametrize('environment', ['production', 'development', 'testing'])
def test_remote_flag_never_enables_other_environments(application, client, course, gateway,
                                                     monkeypatch, environment):
    monkeypatch.setitem(application.config, 'APP_ENV', environment)
    assert 'name="payment_method"' not in client.get(COURSE_URL).text
    assert enroll(client, course).status_code == 200
    assert client.post(BASE+'/notification', json={}).status_code == 404
    gateway[0].assert_not_called()


def test_callback_basic_auth_exception_is_disabled_with_flag(application, course, monkeypatch):
    monkeypatch.setitem(application.config, 'NEXI_COURSE_SANDBOX_ENABLED', False)
    assert application.test_client().post(BASE+'/notification', json={}).status_code == 401


def test_course_test_mode_never_changes_calendar_config_or_calls_calendar(application, authenticated_client,
                                                                         course, gateway, monkeypatch):
    monkeypatch.setitem(application.config, 'GOOGLE_CALENDAR_ID', 'synthetic-calendar-id')
    calendar = Mock(side_effect=AssertionError('Calendar must not be called'))
    monkeypatch.setattr(site, '_ottieni_servizio_calendario', calendar)
    enroll(authenticated_client, course)
    payment = attempt()
    gateway[1].return_value = {'operations': [operation(payment)]}
    assert notify(application.test_client(), payment).status_code == 200
    calendar.assert_not_called()
    assert application.config['GOOGLE_CALENDAR_ID'] == 'synthetic-calendar-id'


def test_missing_remote_key_does_not_fall_back_to_isolated_key(application, authenticated_client,
                                                              course, gateway, monkeypatch):
    monkeypatch.setitem(application.config, 'NEXI_COURSE_SANDBOX_API_KEY', None)
    assert enroll(authenticated_client, course).status_code == 200
    gateway[0].assert_not_called()


@pytest.mark.parametrize('late_result', ['AUTHORIZED', 'DECLINED', 'EXECUTED'])
def test_return_cannot_overwrite_a_concurrent_notification(
        application, authenticated_client, course, gateway, late_result):
    enroll(authenticated_client, course)
    payment = attempt()
    success = operation(payment)
    late = operation(payment, operationResult=late_result)
    result_path = BASE + '/result/' + payment.access_token
    outer_session = site.db.session()

    def read_while_notification_arrives(order_id):
        gateway[1].side_effect = None
        gateway[1].return_value = {'operations': [success]}
        # The browser request has loaded the pending attempt and is waiting for Nexi.
        # Complete the callback in a separate transaction before returning the old result.
        with application.app_context():
            assert site.db.session() is not outer_session
            response = application.test_client().post(BASE + '/notification', json={
                'operation': success, 'securityToken': SECURITY_TOKEN,
            })
            assert response.status_code == 200
        return {'operations': [late]}

    gateway[1].side_effect = read_while_notification_arrives
    response = authenticated_client.get(result_path)
    assert response.status_code == 200 and 'Iscrizione confermata' in response.text
    site.db.session.refresh(payment)
    assert payment.status == 'confirmed'
    assert payment.registration.stato == 'Confermato'
    assert payment.operation_id == success['operationId']
    assert site.EmailOperativa.query.filter_by(entita_tipo='IscrizioneCorso').count() == 1
