import json
import re
from unittest.mock import Mock
from werkzeug.security import generate_password_hash

import pytest

import app as site
from config import TestingConfig
from nexi_gateway import NexiError, NexiSandboxClient, token_digest


SECURITY_TOKEN = 'synthetic-course-notification-token'
CHECKOUT = 'https://xpaysandbox.nexigroup.com/checkout/synthetic-course'
BASE = '/payments/nexi/sandbox/courses'
COURSE_URL = '/iscrizione-corsi/disostruzione-pediatrica'


@pytest.fixture
def application(monkeypatch):
    site.app.config.from_object(TestingConfig)
    monkeypatch.setattr(site, 'invia_email_alert_nuova_iscrizione', Mock(return_value=True))
    for key, value in {
        'NEXI_SANDBOX_ENABLED': True, 'NEXI_SANDBOX_ISOLATED': True,
        'NEXI_SANDBOX_API_KEY': 'synthetic-key', 'PUBLIC_BASE_URL': 'https://sandbox.example.invalid',
    }.items():
        monkeypatch.setitem(site.app.config, key, value)
    with site.app.app_context():
        site.db.create_all()
        yield site.app
        site.db.session.remove()
        site.db.drop_all()


@pytest.fixture
def client(application):
    return application.test_client()


@pytest.fixture
def course(application):
    result = site.Corso(
        titolo='Disostruzione · prova', tipo='disostruzione-pediatrica',
        data=(site.local_today() + site.timedelta(days=30)).isoformat(),
        ora='10:00', luogo='Sede di prova', stato='Aperto', capienza_massima=10,
    )
    site.db.session.add(result)
    site.db.session.commit()
    return result


@pytest.fixture
def gateway(monkeypatch):
    create = Mock(return_value=(CHECKOUT, token_digest(SECURITY_TOKEN)))
    read = Mock(return_value={'operations': []})
    monkeypatch.setattr(NexiSandboxClient, 'create_checkout', create)
    monkeypatch.setattr(NexiSandboxClient, 'get_order', read)
    return create, read


def csrf(client, path=COURSE_URL):
    return re.search(r'name="_csrf_token" value="([^"]+)"', client.get(path).text).group(1)


def enroll(client, course, **changes):
    form = {
        '_csrf_token': csrf(client), 'payment_method': 'nexi_sandbox',
        'nome': 'Partecipante di prova', 'codice_fiscale': 'TESTONLY00000000',
        'telefono': '3330000000', 'email': 'prova@example.invalid',
        'partecipazione': 'Singolo 34 euro', 'data_corso': str(course.id),
        'scopo_informativo': 'on', 'no_certificazione': 'on', 'buono_stato_salute': 'on',
        'consenso_privacy': 'on', 'condizioni_corso': 'on',
    }
    form.update(changes)
    return client.post(COURSE_URL, data=form)


def attempt():
    return site.SandboxCoursePaymentAttempt.query.order_by(site.SandboxCoursePaymentAttempt.id.desc()).first()


def operation(payment, **changes):
    result = {
        'orderId': payment.order_id, 'operationId': 'synthetic-course-operation',
        'operationType': 'AUTHORIZATION', 'operationResult': 'EXECUTED',
        'operationAmount': str(payment.amount_cents), 'operationCurrency': 'EUR',
    }
    result.update(changes)
    return result


def notify(client, payment, **changes):
    payload = {'operation': operation(payment), 'securityToken': SECURITY_TOKEN}
    payload.update(changes)
    return client.post(BASE + '/notification', json=payload)


@pytest.mark.parametrize('participation,seats,amount', [
    ('Singolo 34 euro', 1, 3400), ('Coppia 60 euro', 2, 6000),
])
def test_server_prices_and_seats_saved_before_gateway(client, course, gateway, participation, seats, amount):
    def create(*args, **kwargs):
        payment = attempt()
        assert payment.registration.posti == seats
        assert payment.amount_cents == amount
        assert site.IscrizioneCorso.query.count() == 1
        return CHECKOUT, token_digest(SECURITY_TOKEN)
    gateway[0].side_effect = create
    response = enroll(client, course, partecipazione=participation,
                      nome_secondo_partecipante='Secondo partecipante di prova', amount='1', prezzo='1')
    assert response.status_code == 303 and response.location == CHECKOUT
    payment = attempt()
    gateway[0].assert_called_once_with(payment.order_id, amount, 'https://sandbox.example.invalid',
                                       payment.access_token, checkout_kind='course')
    assert payment.registration.stato == 'Nuova'
    assert payment.security_token_hash == token_digest(SECURITY_TOKEN)


@pytest.mark.parametrize('changes', [
    {'_csrf_token': 'wrong'}, {'condizioni_corso': ''}, {'partecipazione': 'Coppia 60 euro'},
    {'partecipazione': 'Singolo 1 euro'},
])
def test_invalid_forms_do_not_create_orders(client, course, gateway, changes):
    assert enroll(client, course, **changes).status_code == 200
    assert site.IscrizioneCorso.query.count() == 0
    gateway[0].assert_not_called()


@pytest.mark.parametrize('key,value', [
    ('APP_ENV', 'production'), ('APP_ENV', 'development'), ('APP_ENV', 'staging'),
    ('NEXI_SANDBOX_ENABLED', False), ('NEXI_SANDBOX_API_KEY', None),
    ('MAIL_SUPPRESS_SEND', False), ('GOOGLE_CALENDAR_ID', 'synthetic'),
])
def test_course_payments_fail_closed(application, client, course, gateway, monkeypatch, key, value):
    monkeypatch.setitem(application.config, key, value)
    assert 'name="payment_method"' not in client.get(COURSE_URL).text
    if value == 'staging':
        assert client.post(COURSE_URL, data={'payment_method': 'nexi_sandbox'}).status_code == 401
    else:
        assert enroll(client, course).status_code == 200
    gateway[0].assert_not_called()
    assert site.IscrizioneCorso.query.count() == 0


def test_full_course_waitlist_never_opens_checkout(client, course, gateway):
    course.capienza_massima = 1
    site.db.session.commit()
    assert enroll(client, course, partecipazione='Coppia 60 euro',
                  nome_secondo_partecipante='Secondo partecipante di prova').status_code == 303
    assert site._posti_attivi_corso(course.id) == 2  # Existing last-place rule.
    response = enroll(client, course)
    assert response.status_code == 302 and 'lista_attesa=1' in response.location
    assert site.IscrizioneCorso.query.order_by(site.IscrizioneCorso.id.desc()).first().posti == 0
    assert site.SandboxCoursePaymentAttempt.query.count() == 1
    gateway[0].assert_called_once()


def test_no_dates_show_interest_only(client, course, gateway):
    course.stato = 'Annullato'
    site.db.session.commit()
    page = client.get(COURSE_URL).text
    assert 'name="payment_method"' not in page
    assert 'course-interest-form' in page
    gateway[0].assert_not_called()


def test_paid_course_keeps_manual_confirmation_and_repeated_callback_is_idempotent(client, course, gateway):
    enroll(client, course)
    payment = attempt()
    gateway[1].return_value = {'operations': [operation(payment)]}
    assert notify(client, payment).status_code == 200
    assert payment.status == 'confirmed' and payment.registration.stato == 'Nuova'
    assert payment.registration.posti == 1
    assert notify(client, payment).status_code == 200
    page = client.get(BASE + '/result/' + payment.access_token + '?esito=KO&cancel=1')
    assert 'Pagamento simulato confermato' in page.text
    assert page.headers['Cache-Control'].startswith('no-store')
    assert page.headers['Referrer-Policy'] == 'no-referrer'
    assert 'noindex' in page.headers['X-Robots-Tag']
    assert site.RegistroEvento.query.filter_by(categoria='nexi_course_sandbox', esito='successo').count() == 1
    gateway[1].assert_called_once_with(payment.order_id)


def test_forged_notification_rejected(client, course, gateway):
    enroll(client, course)
    payment = attempt()
    assert notify(client, payment, securityToken='synthetic-forged-token').status_code == 403
    assert payment.status == 'pending'
    gateway[1].assert_not_called()


def test_admin_can_review_payment_without_automatic_enrollment_confirmation(client, course, gateway):
    enroll(client, course)
    payment = attempt()
    gateway[1].return_value = {'operations': [operation(payment)]}
    notify(client, payment)
    path = f'/admin/pratica/IscrizioneCorso/{payment.registration_id}'
    assert client.get(path).status_code == 302
    admin = site.Admin(username='synthetic-admin', password=generate_password_hash('synthetic-password'))
    site.db.session.add(admin)
    site.db.session.commit()
    login = client.post('/admin/login', data={
        '_csrf_token': csrf(client, '/admin/login'),
        'username': 'synthetic-admin', 'password': 'synthetic-password',
    })
    assert login.status_code == 302
    response = client.get(path)
    assert response.status_code == 200
    assert 'Pagamento Nexi di prova' in response.text
    assert payment.order_id in response.text and '34,00 €' in response.text
    assert payment.registration.stato == 'Nuova'


@pytest.mark.parametrize('changes', [{'operationAmount': '1'}, {'operationCurrency': 'USD'}, {'orderId': 'NX'+'a'*16}])
def test_independent_gateway_must_match_purchase(client, course, gateway, changes):
    enroll(client, course)
    payment = attempt()
    gateway[1].return_value = {'operations': [operation(payment, **changes)]}
    assert notify(client, payment).status_code == 503
    assert payment.status == 'pending'


@pytest.mark.parametrize('change', ['cancel', 'move', 'participation', 'terms', 'archive'])
def test_changed_registration_or_course_requires_review(client, course, gateway, change):
    enroll(client, course)
    payment = attempt()
    registration = payment.registration
    if change == 'cancel': registration.stato = 'Annullato'
    if change == 'archive': course.archiviato_il = site.utc_now()
    if change == 'move': course.data = (site.local_today() + site.timedelta(days=31)).isoformat()
    if change == 'participation': registration.partecipazione = 'Coppia 60 euro'
    if change == 'terms': registration.dati_extra = json.dumps({'condizioni_corso_versione': 'changed'})
    site.db.session.commit()
    gateway[1].return_value = {'operations': [operation(payment)]}
    assert notify(client, payment).status_code == 200
    assert payment.status == 'review'


def test_authorization_does_not_confirm_payment(client, course, gateway):
    enroll(client, course)
    payment = attempt()
    gateway[1].return_value = {'operations': [operation(payment, operationResult='AUTHORIZED')]}
    assert notify(client, payment).status_code == 200
    assert payment.status == 'authorized'


def test_failed_payment_retries_same_registration_with_csrf(client, course, gateway):
    enroll(client, course)
    first = attempt()
    gateway[1].return_value = {'operations': [operation(first, operationResult='CANCELED')]}
    notify(client, first)
    retry_url = BASE + '/result/' + first.access_token + '/retry'
    assert client.get(retry_url).status_code == 405
    assert client.post(retry_url, data={'_csrf_token': 'wrong'}).status_code == 400
    token = csrf(client, BASE + '/result/' + first.access_token)
    assert client.post(retry_url, data={'_csrf_token': token}).status_code == 303
    assert site.IscrizioneCorso.query.count() == 1
    assert site.SandboxCoursePaymentAttempt.query.count() == 2
    second = attempt()
    assert second.order_id != first.order_id and second.registration_id == first.registration_id
    assert client.post(retry_url, data={'_csrf_token': token}).status_code == 303
    assert site.SandboxCoursePaymentAttempt.query.count() == 2
    # A delayed success on the old order cannot silently confirm a duplicate purchase.
    gateway[1].return_value = {'operations': [operation(first)]}
    assert notify(client, first).status_code == 200
    assert first.status == 'review' and second.status == 'pending'


@pytest.mark.parametrize('uncertain,expected', [(True, 'uncertain'), (False, 'initialization_failed')])
def test_initialization_failure_preserves_registration(client, course, gateway, uncertain, expected):
    gateway[0].side_effect = NexiError(status=503 if uncertain else 401, uncertain=uncertain)
    response = enroll(client, course)
    assert response.status_code == 303
    payment = attempt()
    assert payment.status == expected and site.IscrizioneCorso.query.count() == 1
    token = csrf(client, COURSE_URL if uncertain else response.location)
    response = client.post(response.location + '/retry', data={'_csrf_token': token})
    assert response.status_code == 303
    assert gateway[0].call_count == (1 if uncertain else 2)


def test_false_browser_success_and_gateway_outage_do_not_confirm(client, course, gateway):
    enroll(client, course)
    payment = attempt()
    gateway[1].side_effect = NexiError(uncertain=True)
    page = client.get(BASE + '/result/' + payment.access_token + '?esito=OK')
    assert page.status_code == 200 and 'temporaneamente non disponibile' in page.text
    assert payment.status == 'pending'
    assert notify(client, payment).status_code == 503


def test_alert_email_failure_does_not_prevent_checkout(client, course, gateway, monkeypatch):
    monkeypatch.setattr(site, 'invia_email_alert_nuova_iscrizione', Mock(side_effect=RuntimeError('synthetic')))
    assert enroll(client, course).status_code == 303
    assert site.IscrizioneCorso.query.count() == site.SandboxCoursePaymentAttempt.query.count() == 1


def test_gateway_separates_course_callbacks_from_sleep(monkeypatch):
    transport = Mock(return_value={'hostedPage': CHECKOUT, 'securityToken': SECURITY_TOKEN})
    monkeypatch.setattr(NexiSandboxClient, '_request', transport)
    NexiSandboxClient('synthetic').create_checkout('NX'+'b'*16, 6000, 'https://sandbox.example.invalid',
                                                 'a'*64, checkout_kind='course')
    session = transport.call_args.args[2]['paymentSession']
    assert '/courses/result/' in session['resultUrl']
    assert session['notificationUrl'].endswith('/courses/notification')
