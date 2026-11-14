"""Disposable Nexi checkout for choking-prevention course registrations."""

from datetime import datetime, timedelta
import json
import secrets
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from nexi_gateway import NexiError, NexiSandboxClient, ORDER_PATTERN, safe_checkout_url, token_digest
from payment_sandbox import (
    FAILURE_RESULTS, TOKEN_PATTERN, sandbox_enabled, sandbox_ready, utc_now,
    verified_order_operations,
)


COURSE_PRICES = {'Singolo 34 euro': 3400, 'Coppia 60 euro': 6000}


def purchase_digest(registration):
    course = registration.corso
    extra = registration.extra_dict()
    return token_digest(json.dumps({
        'course_id': registration.corso_id,
        'date': course.data if course else None,
        'time': course.ora if course else None,
        'location': course.luogo if course else None,
        'participation': registration.partecipazione,
        'seats': registration.posti,
        'requested_seats': registration.posti_richiesti,
        'terms': extra.get('condizioni_corso_versione'),
        'accepted_at': extra.get('condizioni_corso_accettate_il'),
    }, sort_keys=True))


def registration_eligible(registration):
    if registration is None:
        return False
    course = registration.corso
    expected_seats = 2 if registration.partecipazione == 'Coppia 60 euro' else 1
    return bool(
        registration.corso_tipo == 'disostruzione-pediatrica'
        and registration.partecipazione in COURSE_PRICES
        and registration.tipo_richiesta == 'richiesta_iscrizione'
        and registration.stato in {'Nuova', 'Confermato'}
        and registration.archiviata_il is None and registration.dati_anonimizzati_il is None
        and registration.posti == registration.posti_richiesti == expected_seats
        and registration.extra_dict().get('condizioni_corso_versione')
        and registration.extra_dict().get('condizioni_corso_accettate_il')
        and course and course.tipo == 'disostruzione-pediatrica'
        and course.stato in {'Aperto', 'Completo'} and course.archiviato_il is None
        and course.data >= datetime.now(ZoneInfo('Europe/Rome')).date().isoformat()
    )


def register_course_payment_sandbox(app, db, registration_model, payment_model, validate_csrf, record_event, limit):
    blueprint = Blueprint('nexi_course_sandbox', __name__, url_prefix='/payments/nexi/sandbox/courses')

    def client():
        return NexiSandboxClient(current_app.config.get('NEXI_SANDBOX_API_KEY'))

    def record_error(payment, message):
        record_event('nexi_course_sandbox', 'errore', message, 'IscrizioneCorso',
                     payment.registration_id, {'order_id': payment.order_id})

    def result_location(payment):
        return url_for('nexi_course_sandbox.result', access_token=payment.access_token)

    def start_checkout(registration):
        if not sandbox_ready():
            abort(404)
        existing = payment_model.query.filter(
            payment_model.registration_id == registration.id,
            db.or_(payment_model.active_registration_id == registration.id,
                   payment_model.status == 'confirmed'),
        ).order_by(payment_model.id.desc()).first()
        if existing:
            return redirect(result_location(existing), code=303)
        if not registration_eligible(registration):
            abort(409)
        payment = payment_model(
            registration_id=registration.id, active_registration_id=registration.id,
            order_id='NX' + secrets.token_hex(8), access_token=secrets.token_urlsafe(48),
            amount_cents=COURSE_PRICES[registration.partecipazione], currency='EUR',
            participation=registration.partecipazione, purchase_digest=purchase_digest(registration),
            status='creating', expires_at=utc_now() + timedelta(minutes=15),
        )
        db.session.add(payment)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = payment_model.query.filter_by(active_registration_id=registration.id).first()
            if not existing:
                abort(409)
            return redirect(result_location(existing), code=303)
        try:
            payment.checkout_url, payment.security_token_hash = client().create_checkout(
                payment.order_id, payment.amount_cents, current_app.config['PUBLIC_BASE_URL'],
                payment.access_token, checkout_kind='course',
            )
            payment.status = 'pending'
        except NexiError as error:
            payment.status = 'uncertain' if error.uncertain else 'initialization_failed'
            if not error.uncertain:
                payment.active_registration_id = None
            db.session.commit()
            record_error(payment, 'Avvio Nexi non riuscito: iscrizione di prova conservata.')
            return redirect(result_location(payment), code=303)
        db.session.commit()
        return redirect(payment.checkout_url, code=303)

    def reconcile(payment):
        if payment.status in {'confirmed', 'review'}:
            return
        operations = verified_order_operations(payment, client().get_order(payment.order_id))
        successful = [op for op in operations if op.get('operationResult') == 'EXECUTED']
        payment.verified_at = utc_now()
        if successful:
            registration = registration_model.query.filter_by(id=payment.registration_id).with_for_update().first()
            other = payment_model.query.filter(
                payment_model.registration_id == payment.registration_id,
                payment_model.id != payment.id,
                db.or_(payment_model.active_registration_id == payment.registration_id,
                       payment_model.status == 'confirmed'),
            ).first()
            if (
                len(successful) != 1 or other or not registration_eligible(registration)
                or purchase_digest(registration) != payment.purchase_digest
                or COURSE_PRICES.get(registration.partecipazione) != payment.amount_cents
            ):
                payment.status = 'review'
                db.session.commit()
                record_error(payment, 'Pagamento di prova ricevuto; iscrizione o corso da verificare manualmente.')
                return
            # Payment and enrollment confirmation are deliberately separate.
            # Enrollment keeps its existing state, seats, and manual confirmation.
            updated = payment_model.query.filter(
                payment_model.id == payment.id,
                payment_model.status.notin_(['confirmed', 'review']),
            ).update({
                payment_model.status: 'confirmed',
                payment_model.active_registration_id: None,
                payment_model.operation_id: successful[0]['operationId'],
                payment_model.verified_at: utc_now(),
            }, synchronize_session=False)
            db.session.commit()
            db.session.refresh(payment)
            if updated:
                record_event('nexi_course_sandbox', 'successo', 'Pagamento corso di prova verificato.',
                             'IscrizioneCorso', registration.id, {'order_id': payment.order_id})
            return
        if any(op.get('operationResult') == 'AUTHORIZED' for op in operations):
            payment.status = 'authorized'
        elif operations and all(op.get('operationResult') in FAILURE_RESULTS for op in operations):
            payment.status = 'failed'
            payment.active_registration_id = None
        elif not operations and payment.expires_at + timedelta(minutes=5) < utc_now():
            payment.status = 'review'
        db.session.commit()

    @blueprint.before_request
    def require_isolation():
        if not sandbox_enabled():
            abort(404)

    @blueprint.after_request
    def private_response(response):
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
                record_error(payment, 'Verifica del pagamento corso Nexi temporaneamente non disponibile.')
        registration = db.session.get(registration_model, payment.registration_id)
        return render_template(
            'nexi_course_sandbox_result.html', payment=payment, registration=registration,
            verification_unavailable=unavailable,
            retry_available=payment.status in {'failed', 'initialization_failed'} and registration_eligible(registration),
            checkout_available=payment.status == 'pending' and payment.expires_at > utc_now()
            and safe_checkout_url(payment.checkout_url),
        )

    @blueprint.route('/result/<access_token>/retry', methods=['POST'])
    @limit('5 per minute', methods=['POST'])
    def retry(access_token):
        if not validate_csrf():
            abort(400)
        if not TOKEN_PATTERN.fullmatch(access_token):
            abort(404)
        payment = payment_model.query.filter_by(access_token=access_token).first_or_404()
        if payment.status not in {'failed', 'initialization_failed'}:
            return redirect(result_location(payment), code=303)
        return start_checkout(db.session.get(registration_model, payment.registration_id))

    @blueprint.route('/notification', methods=['POST'])
    def notification():
        request.max_content_length = 32768
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('operation'), dict):
            abort(400)
        order_id, supplied = body['operation'].get('orderId'), body.get('securityToken')
        if (
            not isinstance(order_id, str) or not ORDER_PATTERN.fullmatch(order_id)
            or not isinstance(supplied, str) or not 16 <= len(supplied) <= 512
        ):
            abort(400)
        payment = payment_model.query.filter_by(order_id=order_id).first()
        if not payment or not payment.security_token_hash or not secrets.compare_digest(
            token_digest(supplied), payment.security_token_hash,
        ):
            abort(403)
        try:
            reconcile(payment)
        except NexiError:
            record_error(payment, 'Notifica corso ricevuta: verifica indipendente Nexi non disponibile.')
            abort(503)
        return '', 200

    app.register_blueprint(blueprint)
    return {'ready': sandbox_ready, 'start_checkout': start_checkout}
