"""Isolated sleep-offer checkout: no production endpoint or real integrations."""

from datetime import datetime, timedelta, timezone
import re
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from nexi_gateway import (
    NexiError, NexiSandboxClient, ORDER_PATTERN, safe_checkout_url,
    token_digest, valid_public_origin,
)


FAILURE_RESULTS = {'DECLINED', 'CANCELED', 'CANCELLED', 'THREEDS_FAILED', 'DENIED_BY_RISK', 'FAILED'}
TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9_-]{64}$')


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sandbox_enabled():
    config = current_app.config
    return bool(
        config.get('NEXI_SANDBOX_ENABLED')
        and config.get('NEXI_SANDBOX_ISOLATED')
        and config.get('APP_ENV') in {'payment_sandbox', 'testing'}
        and config.get('SQLALCHEMY_DATABASE_URI') == 'sqlite:///:memory:'
        and config.get('MAIL_SUPPRESS_SEND')
        and not config.get('GOOGLE_CALENDAR_ID')
        and not config.get('GOOGLE_SERVICE_ACCOUNT_FILE')
        and str(current_app.extensions['sqlalchemy'].engine.url) == 'sqlite:///:memory:'
    )


def sandbox_ready():
    return bool(
        sandbox_enabled()
        and current_app.config.get('NEXI_SANDBOX_API_KEY')
        and valid_public_origin(current_app.config.get('PUBLIC_BASE_URL'))
    )


def register_payment_sandbox(app, db, call_model, payment_model, send_questionnaire, record_event):
    blueprint = Blueprint('nexi_sandbox', __name__, url_prefix='/payments/nexi/sandbox')

    def client():
        return NexiSandboxClient(current_app.config.get('NEXI_SANDBOX_API_KEY'))

    def record_error(payment, message):
        record_event(
            'nexi_sandbox', 'errore', message, 'CallSonno', payment.sleep_call_id,
            {'order_id': payment.order_id},
        )

    def active_payment(call_id):
        if not sandbox_enabled():
            return None
        return payment_model.query.filter_by(active_call_id=call_id).first()

    def result_location(payment):
        return url_for('nexi_sandbox.result', access_token=payment.access_token)

    def start_checkout(call):
        if not sandbox_ready():
            abort(404)
        existing = active_payment(call.id)
        if existing:
            return redirect(result_location(existing), code=303)
        payment = payment_model(
            order_id='NX' + secrets.token_hex(8),
            access_token=secrets.token_urlsafe(48),
            sleep_call_id=call.id,
            active_call_id=call.id,
            amount_cents=call.prezzo_centesimi,
            currency='EUR',
            formula=call.formula_scelta,
            terms_version=call.condizioni_versione,
            accepted_at=call.condizioni_accettate_il,
            proposal_digest=token_digest(call.proposta_token),
            status='creating',
            expires_at=utc_now() + timedelta(minutes=15),
        )
        db.session.add(payment)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = active_payment(call.id)
            if not existing:
                abort(409)
            return redirect(result_location(existing), code=303)
        try:
            checkout_url, security_hash = client().create_checkout(
                payment.order_id, payment.amount_cents,
                current_app.config['PUBLIC_BASE_URL'], payment.access_token,
            )
        except NexiError as error:
            payment.status = 'uncertain' if error.uncertain else 'initialization_failed'
            if not error.uncertain:
                payment.active_call_id = None
            db.session.commit()
            record_error(payment, 'Avvio del pagamento sandbox non riuscito; verificare il tentativo prima di riprovare.')
            return redirect(result_location(payment), code=303)
        payment.checkout_url = checkout_url
        payment.security_token_hash = security_hash
        payment.status = 'pending'
        db.session.commit()
        return redirect(checkout_url, code=303)

    def confirm_payment(payment, operation):
        call = db.session.get(call_model, payment.sleep_call_id)
        if not call or token_digest(call.proposta_token or '') != payment.proposal_digest:
            payment.status = 'review'
            db.session.commit()
            record_error(payment, 'Pagamento simulato verificato, ma la proposta è cambiata: controllo manuale necessario.')
            return
        confirmed_at = utc_now()
        updated = call_model.query.filter(
            call_model.id == call.id,
            call_model.pagamento_confermato_il.is_(None),
            call_model.proposta_revocata_il.is_(None),
            call_model.metodo_pagamento == 'nexi_sandbox',
            call_model.prezzo_centesimi == payment.amount_cents,
            call_model.formula_scelta == payment.formula,
            call_model.condizioni_versione == payment.terms_version,
            call_model.condizioni_accettate_il == payment.accepted_at,
        ).update({
            call_model.stato_pagamento: 'Confermato',
            call_model.riferimento_pagamento: payment.order_id,
            call_model.pagamento_confermato_il: confirmed_at,
            call_model.token_questionario: call.token_questionario or secrets.token_urlsafe(48),
            call_model.questionario_inviato_il: confirmed_at,
        }, synchronize_session=False)
        payment.operation_id = operation['operationId']
        payment.verified_at = confirmed_at
        if updated or call.riferimento_pagamento == payment.order_id:
            payment.status = 'confirmed'
            payment.active_call_id = None
        else:
            payment.status = 'review'
        db.session.commit()
        if updated:
            db.session.expire(call)
            try:
                sent = send_questionnaire(call)
            except Exception:
                sent = False
            if not sent:
                record_error(payment, 'Pagamento simulato salvato; invio del questionario non riuscito.')
        elif payment.status == 'review':
            record_error(payment, 'Pagamento simulato verificato, ma i dati della pratica non corrispondono.')

    def reconcile(payment):
        if payment.status in {'confirmed', 'review'}:
            return
        result = client().get_order(payment.order_id)
        operations = result.get('operations')
        if not isinstance(operations, list):
            raise NexiError(uncertain=True)
        matching = []
        for operation in operations:
            if not isinstance(operation, dict):
                raise NexiError(uncertain=True)
            if operation.get('operationType') not in {'AUTHORIZATION', 'CAPTURE'}:
                continue
            amount = operation.get('operationAmount')
            operation_id = operation.get('operationId')
            if (
                operation.get('orderId') != payment.order_id
                or operation.get('operationCurrency') != payment.currency
                or not isinstance(amount, str) or not amount.isascii() or not amount.isdigit()
                or int(amount) != payment.amount_cents
                or not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 120
            ):
                record_error(payment, 'Esito sandbox non coerente con ordine, importo o valuta; nessuna conferma.')
                raise NexiError(uncertain=True)
            matching.append(operation)
        successful = [op for op in matching if op.get('operationResult') == 'EXECUTED']
        if len(successful) == 1:
            confirm_payment(payment, successful[0])
            return
        if len(successful) > 1:
            payment.status = 'review'
            db.session.commit()
            record_error(payment, 'Più operazioni riuscite per lo stesso ordine sandbox: controllo manuale necessario.')
            return
        payment.verified_at = utc_now()
        if any(op.get('operationResult') == 'AUTHORIZED' for op in matching):
            payment.status = 'authorized'
        elif matching and all(op.get('operationResult') in FAILURE_RESULTS for op in matching):
            payment.status = 'failed'
            payment.active_call_id = None
        elif not matching and payment.expires_at + timedelta(minutes=5) < utc_now():
            # A lost initialization response must remain reconcilable, not silently retried.
            payment.status = 'review'
        db.session.commit()

    @blueprint.before_request
    def require_isolation():
        if not sandbox_enabled():
            abort(404)

    @blueprint.after_request
    def protect_payment_pages(response):
        response.headers['Cache-Control'] = 'no-store, private, max-age=0'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @blueprint.route('/result/<access_token>')
    def result(access_token):
        if not TOKEN_PATTERN.fullmatch(access_token):
            abort(404)
        payment = payment_model.query.filter_by(access_token=access_token).first_or_404()
        unavailable = False
        if payment.status != 'initialization_failed':
            try:
                reconcile(payment)
            except NexiError:
                unavailable = True
                record_error(payment, 'Verifica dello stato Nexi sandbox temporaneamente non disponibile.')
        return render_template(
            'nexi_sandbox_result.html', payment=payment,
            call=db.session.get(call_model, payment.sleep_call_id),
            verification_unavailable=unavailable,
            checkout_available=bool(
                payment.status == 'pending' and payment.expires_at > utc_now()
                and safe_checkout_url(payment.checkout_url)
            ),
        )

    @blueprint.route('/notification', methods=['POST'])
    def notification():
        request.max_content_length = 32768
        if request.content_length is not None and request.content_length > 32768:
            abort(413)
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('operation'), dict):
            abort(400)
        order_id = body['operation'].get('orderId')
        supplied = body.get('securityToken')
        if (
            not isinstance(order_id, str) or not ORDER_PATTERN.fullmatch(order_id)
            or not isinstance(supplied, str) or not 16 <= len(supplied) <= 512
        ):
            abort(400)
        payment = payment_model.query.filter_by(order_id=order_id).first()
        if (
            payment is None or not payment.security_token_hash
            or not secrets.compare_digest(token_digest(supplied), payment.security_token_hash)
        ):
            abort(403)
        try:
            reconcile(payment)
        except NexiError:
            record_error(payment, 'Notifica ricevuta; verifica indipendente dello stato Nexi sandbox non riuscita.')
            abort(503)
        return '', 200

    app.register_blueprint(blueprint)
    return {
        'enabled': sandbox_enabled, 'ready': sandbox_ready,
        'active_payment': active_payment, 'start_checkout': start_checkout,
        'result_location': result_location,
    }
