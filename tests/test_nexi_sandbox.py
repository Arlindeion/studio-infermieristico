import json
import re
import secrets
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

import app as site
from config import TestingConfig, PaymentSandboxConfig
from nexi_gateway import NexiError, NexiSandboxClient, safe_checkout_url, token_digest
import nexi_gateway


GATEWAY_TOKEN = 'synthetic-notification-token-only'
CHECKOUT_URL = 'https://xpaysandbox.nexigroup.com/checkout/synthetic'


@pytest.fixture
def application(monkeypatch):
    site.app.config.from_object(TestingConfig)
    monkeypatch.setitem(site.app.config, 'NEXI_SANDBOX_ENABLED', True)
    monkeypatch.setitem(site.app.config, 'NEXI_SANDBOX_ISOLATED', True)
    monkeypatch.setitem(site.app.config, 'NEXI_SANDBOX_API_KEY', 'synthetic-api-key')
    monkeypatch.setitem(site.app.config, 'PUBLIC_BASE_URL', 'https://sandbox.example.invalid')
    with site.app.app_context():
        site.db.create_all()
        yield site.app
        site.db.session.remove()
        site.db.drop_all()


@pytest.fixture
def client(application):
    return application.test_client()


@pytest.fixture
def proposal(application):
    call = site.CallSonno(
        nome='Famiglia di prova', telefono='0000000000', email='famiglia@example.invalid',
        eta_bambino_mesi=8, difficolta_principale='Prova sintetica',
        consenso_privacy=True, data='2026-12-01', ora='10:00', stato='Conclusa',
        proposta_tipo='percorso', proposta_token=secrets.token_urlsafe(48),
        proposta_scade_il=site.utc_now() + site.timedelta(days=7),
    )
    site.db.session.add(call)
    site.db.session.commit()
    return call


@pytest.fixture
def gateway(monkeypatch):
    create = Mock(return_value=(CHECKOUT_URL, token_digest(GATEWAY_TOKEN)))
    get = Mock(return_value={'operations': []})
    monkeypatch.setattr(NexiSandboxClient, 'create_checkout', create)
    monkeypatch.setattr(NexiSandboxClient, 'get_order', get)
    return create, get


def start(client, proposal, **changes):
    page = client.get(f'/offerta-sonno/{proposal.proposta_token}?modifica=1')
    token = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    form = {
        '_csrf_token': token, 'formula_scelta': 'percorso',
        'metodo_pagamento': 'nexi_sandbox', 'condizioni_sonno': 'on',
    }
    form.update(changes)
    return client.post(f'/offerta-sonno/{proposal.proposta_token}', data=form)


def operation(payment, **changes):
    result = {
        'orderId': payment.order_id, 'operationId': 'synthetic-operation-1',
        'operationAmount': str(payment.amount_cents), 'operationCurrency': 'EUR',
        'operationType': 'AUTHORIZATION', 'operationResult': 'EXECUTED',
    }
    result.update(changes)
    return result


def notify(client, payment, **changes):
    body = {
        'eventId': 'synthetic-event-1', 'securityToken': GATEWAY_TOKEN,
        'operation': operation(payment),
    }
    body.update(changes)
    return client.post('/payments/nexi/sandbox/notification', json=body)


def payment_for(proposal):
    return site.SandboxPaymentAttempt.query.filter_by(sleep_call_id=proposal.id).first()


def test_checkout_uses_server_price_and_saves_attempt_before_request(client, proposal, gateway):
    create, _ = gateway
    response = start(client, proposal, prezzo_centesimi='1', importo='1')
    payment = payment_for(proposal)
    assert response.status_code == 303
    assert response.location == CHECKOUT_URL
    assert payment.amount_cents == 20000
    assert payment.active_call_id == proposal.id
    assert payment.security_token_hash == token_digest(GATEWAY_TOKEN)
    assert payment.security_token_hash != GATEWAY_TOKEN
    assert proposal.pagamento_confermato_il is None
    create.assert_called_once_with(
        payment.order_id, 20000, 'https://sandbox.example.invalid', payment.access_token,
    )


@pytest.mark.parametrize('changes', [
    {'_csrf_token': 'wrong'}, {'condizioni_sonno': ''}, {'formula_scelta': 'mirata'},
])
def test_checkout_requires_csrf_terms_and_approved_formula(client, proposal, gateway, changes):
    assert start(client, proposal, **changes).status_code == 400
    gateway[0].assert_not_called()
    assert payment_for(proposal) is None


@pytest.mark.parametrize('key,value', [
    ('NEXI_SANDBOX_ENABLED', False), ('NEXI_SANDBOX_ISOLATED', False),
    ('APP_ENV', 'production'), ('APP_ENV', 'development'),
    ('SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg://invalid/test'),
    ('MAIL_SUPPRESS_SEND', False), ('GOOGLE_CALENDAR_ID', 'synthetic'),
])
def test_sandbox_fails_closed_outside_isolated_environment(application, client, proposal, gateway, monkeypatch, key, value):
    monkeypatch.setitem(application.config, key, value)
    assert 'value="nexi_sandbox"' not in client.get(f'/offerta-sonno/{proposal.proposta_token}').text
    assert start(client, proposal).status_code == 400
    assert client.get('/payments/nexi/sandbox/result/' + 'a' * 64).status_code == 404
    gateway[0].assert_not_called()


def test_default_configuration_has_no_payment_integration():
    assert TestingConfig.NEXI_SANDBOX_ENABLED is False
    assert PaymentSandboxConfig.SQLALCHEMY_DATABASE_URI == 'sqlite:///:memory:'
    assert PaymentSandboxConfig.GOOGLE_CALENDAR_ID is None
    assert PaymentSandboxConfig.GOOGLE_SERVICE_ACCOUNT_FILE is None
    assert PaymentSandboxConfig.MAIL_SUPPRESS_SEND is True


def test_missing_key_does_not_offer_checkout(application, client, proposal, gateway, monkeypatch):
    monkeypatch.setitem(application.config, 'NEXI_SANDBOX_API_KEY', None)
    page = client.get(f'/offerta-sonno/{proposal.proposta_token}')
    assert 'Ambiente di prova' in page.text
    assert 'value="nexi_sandbox"' not in page.text
    assert start(client, proposal).status_code == 400
    gateway[0].assert_not_called()


def test_pending_attempt_prevents_new_checkout_or_offer_changes(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    accepted_at = proposal.condizioni_accettate_il
    response = start(client, proposal, formula_scelta='affiancamento')
    site.db.session.refresh(proposal)
    assert response.location.endswith(payment.access_token)
    assert proposal.prezzo_centesimi == 20000
    assert proposal.formula_scelta == 'percorso'
    assert proposal.condizioni_accettate_il == accepted_at
    assert site.SandboxPaymentAttempt.query.count() == 1
    gateway[0].assert_called_once()


def test_authenticated_callback_verifies_gateway_and_confirms_once(client, proposal, gateway, monkeypatch):
    sender = Mock(return_value=True)
    monkeypatch.setattr(site, 'invia_email_questionario_sonno', sender)
    start(client, proposal)
    payment = payment_for(proposal)
    gateway[1].return_value = {'operations': [operation(payment)]}
    assert notify(client, payment).status_code == 200
    site.db.session.refresh(proposal)
    assert proposal.stato_pagamento == 'Confermato'
    assert proposal.riferimento_pagamento == payment.order_id
    assert proposal.pagamento_confermato_il
    assert proposal.token_questionario
    assert payment.status == 'confirmed'
    assert payment.active_call_id is None
    assert notify(client, payment).status_code == 200
    assert client.get(f'/payments/nexi/sandbox/result/{payment.access_token}').status_code == 200
    sender.assert_called_once()
    gateway[1].assert_called_once_with(payment.order_id)


def test_forged_callback_cannot_trigger_reconciliation(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    assert notify(client, payment, securityToken='forged-token-with-sufficient-length').status_code == 403
    gateway[1].assert_not_called()
    assert proposal.pagamento_confermato_il is None


@pytest.mark.parametrize('changes', [
    {'operationAmount': '1'}, {'operationAmount': 20000}, {'operationCurrency': 'USD'},
    {'orderId': 'NX' + 'f' * 16}, {'operationId': ''},
])
def test_mismatched_gateway_order_never_confirms(client, proposal, gateway, changes):
    start(client, proposal)
    payment = payment_for(proposal)
    gateway[1].return_value = {'operations': [operation(payment, **changes)]}
    assert notify(client, payment).status_code == 503
    assert proposal.pagamento_confermato_il is None
    assert payment.active_call_id == proposal.id


def test_notification_payload_cannot_override_independent_pending_result(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    assert notify(client, payment).status_code == 200
    assert proposal.pagamento_confermato_il is None
    assert payment.status == 'pending'


def test_authorization_is_not_a_completed_payment(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    gateway[1].return_value = {'operations': [operation(payment, operationResult='AUTHORIZED')]}
    assert notify(client, payment).status_code == 200
    assert payment.status == 'authorized'
    assert proposal.pagamento_confermato_il is None


def test_failed_payment_can_be_retried_with_new_order(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    first_order = payment.order_id
    gateway[1].return_value = {'operations': [operation(payment, operationResult='THREEDS_FAILED')]}
    assert notify(client, payment).status_code == 200
    assert payment.status == 'failed'
    assert payment.active_call_id is None
    assert start(client, proposal).status_code == 303
    assert site.SandboxPaymentAttempt.query.count() == 2
    assert site.payment_sandbox['active_payment'](proposal.id).order_id != first_order


def test_late_success_of_old_attempt_does_not_confirm_changed_purchase(client, proposal, gateway):
    start(client, proposal)
    old = payment_for(proposal)
    gateway[1].return_value = {'operations': [operation(old, operationResult='DECLINED')]}
    notify(client, old)
    start(client, proposal, formula_scelta='affiancamento')
    gateway[1].return_value = {'operations': [operation(old)]}
    notify(client, old)
    assert old.status == 'review'
    assert proposal.pagamento_confermato_il is None
    assert proposal.prezzo_centesimi == 32000


def test_timeout_preserves_attempt_and_prevents_duplicate_initialization(client, proposal, gateway):
    gateway[0].side_effect = NexiError(uncertain=True)
    assert start(client, proposal).status_code == 303
    payment = payment_for(proposal)
    assert payment.status == 'uncertain'
    assert payment.active_call_id == proposal.id
    start(client, proposal)
    gateway[0].assert_called_once()


def test_rejected_initialization_can_be_retried(client, proposal, gateway):
    gateway[0].side_effect = NexiError(status=401)
    start(client, proposal)
    payment = payment_for(proposal)
    assert payment.status == 'initialization_failed'
    assert payment.active_call_id is None
    gateway[0].side_effect = None
    start(client, proposal)
    assert site.SandboxPaymentAttempt.query.count() == 2


def test_gateway_outage_does_not_lose_payment_and_return_query_is_not_trusted(client, proposal, gateway):
    start(client, proposal)
    payment = payment_for(proposal)
    gateway[1].side_effect = NexiError(uncertain=True)
    response = client.get(f'/payments/nexi/sandbox/result/{payment.access_token}?esito=OK&cancel=1')
    assert 'non riusciamo a verificare' in response.text
    assert response.headers['Cache-Control'].startswith('no-store')
    assert 'noindex' in response.headers['X-Robots-Tag']
    assert proposal.pagamento_confermato_il is None
    assert notify(client, payment).status_code == 503
    assert site.SandboxPaymentAttempt.query.count() == 1


def test_email_failure_does_not_undo_confirmation(client, proposal, gateway, monkeypatch):
    sender = Mock(side_effect=RuntimeError('synthetic failure'))
    monkeypatch.setattr(site, 'invia_email_questionario_sonno', sender)
    start(client, proposal)
    payment = payment_for(proposal)
    gateway[1].return_value = {'operations': [operation(payment)]}
    assert notify(client, payment).status_code == 200
    site.db.session.refresh(proposal)
    assert proposal.pagamento_confermato_il
    assert payment.status == 'confirmed'
    assert site.RegistroEvento.query.filter_by(categoria='nexi_sandbox', esito='errore').count() >= 1
    notify(client, payment)
    sender.assert_called_once()


@pytest.mark.parametrize('value', [
    'https://example.invalid/pay', 'http://xpaysandbox.nexigroup.com/pay',
    'https://xpaysandbox.nexigroup.com.example.invalid/pay',
    'https://user@xpaysandbox.nexigroup.com/pay', 'https://xpaysandbox.nexigroup.com:444/pay',
    'javascript:alert(1)', None,
])
def test_checkout_url_rejects_external_or_unsafe_destinations(value):
    assert not safe_checkout_url(value)


def test_client_uses_sandbox_integer_cents_and_no_customer_data(monkeypatch):
    result = Mock()
    result.read.return_value = json.dumps({'hostedPage': CHECKOUT_URL, 'securityToken': GATEWAY_TOKEN}).encode()
    context = Mock()
    context.__enter__ = Mock(return_value=result)
    context.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = context
    monkeypatch.setattr(nexi_gateway, 'build_opener', lambda *args: opener)
    url, hashed = NexiSandboxClient('synthetic-key').create_checkout(
        'NX' + 'a' * 16, 20000, 'https://sandbox.example.invalid', 'a' * 64,
    )
    request = opener.open.call_args.args[0]
    payload = json.loads(request.data)
    assert request.full_url.startswith('https://xpaysandbox.nexigroup.com/')
    assert payload['order']['amount'] == '20000'
    assert payload['paymentSession']['captureType'] == 'IMPLICIT'
    assert payload['paymentSession']['notificationUrl'] != payload['paymentSession']['resultUrl']
    assert set(payload['order']) == {'orderId', 'amount', 'currency'}
    assert url == CHECKOUT_URL
    assert hashed == token_digest(GATEWAY_TOKEN)


def test_transport_error_never_includes_key_or_gateway_body(monkeypatch):
    opener = Mock()
    opener.open.side_effect = HTTPError('https://xpaysandbox.nexigroup.com', 401, 'synthetic-secret-key', {}, None)
    monkeypatch.setattr(nexi_gateway, 'build_opener', lambda *args: opener)
    with pytest.raises(NexiError) as caught:
        NexiSandboxClient('synthetic-secret-key').get_order('NX' + 'a' * 16)
    assert caught.value.status == 401
    assert 'synthetic-secret-key' not in str(caught.value)
