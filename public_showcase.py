"""Reversible public brochure mode; booking handlers never run in this mode."""

from datetime import timedelta

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_mail import Message


def showcase_enabled():
    return current_app.config.get('PUBLIC_SITE_MODE') == 'showcase'


def register_public_showcase(app, db, mail, email_model, now, retention_days,
                             validate_csrf, valid_email, valid_phone, record_event,
                             limit):
    blueprint = Blueprint('showcase', __name__)
    public_endpoints = {
        'static', 'healthz', 'homepage', 'chi_siamo', 'faq', 'prestazioni',
        'prima_della_nascita', 'prima_della_nascita_legacy', 'consulenze_online',
        'da_dove_parto', 'privacy', 'condizioni_iscrizione_corsi',
        'condizioni_consulenza_sonno', 'iscrizione_corsi', 'iscrizione_corso',
        'course_interest', 'course_interest_confirmation', 'richiesta_azienda',
        'richiesta_azienda_conferma', 'showcase.interest', 'showcase.confirmation',
    }

    @app.before_request
    def protect_showcase():
        if not showcase_enabled():
            return None
        endpoint = request.endpoint
        if (endpoint is None or endpoint in public_endpoints
                or request.path == '/admin' or request.path.startswith('/admin/')):
            return None
        if request.method in {'GET', 'HEAD'} and endpoint in {'prenota', 'prenota_call_sonno', 'iscrizione_accompagnamento_privata'}:
            destination = {
                'prenota': url_for('prestazioni', _anchor='interesse'),
                'prenota_call_sonno': url_for('consulenze_online', _anchor='interesse'),
                'iscrizione_accompagnamento_privata': url_for('course_interest', tematica='accompagnamento-nascita'),
            }[endpoint]
            return redirect(destination, code=303)
        if request.path.startswith('/api/'):
            return jsonify(error='Le prenotazioni online non sono disponibili.'), 503
        return render_template(
            'errore.html', titolo='Prenotazioni online non disponibili',
            messaggio='Puoi consultare i servizi e inviare una richiesta di interesse. Nessun posto o appuntamento viene riservato online.',
        ), 503

    @app.after_request
    def prevent_stale_booking_pages(response):
        if showcase_enabled() and request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store, private, max-age=0'
        return response

    @blueprint.route('/interesse/<kind>', methods=['POST'])
    @limit('5 per minute', methods=['POST'])
    def interest(kind):
        if not showcase_enabled() or kind not in {'prestazioni', 'sonno'}:
            abort(404)
        if not validate_csrf():
            abort(400)
        name = request.form.get('nome', '').strip()
        phone = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        consent = request.form.get('consenso_privacy') == 'on'
        # Only contact details are accepted: no dates, clinical notes or minors' data.
        if (not name or len(name) > 100 or not valid_phone(phone)
                or len(phone) > 20 or (email and (len(email) > 100 or not valid_email(email)))
                or not consent):
            return render_template('showcase/interest_error.html', kind=kind), 400
        label = 'Prestazioni infermieristiche' if kind == 'prestazioni' else 'Consulenza del sonno'
        recipient = app.config.get('MAIL_ADMIN_RECIPIENT')
        if not recipient:
            abort(503)
        record = email_model(
            entita_tipo='InteresseVetrina', destinatario=recipient,
            oggetto=f'Nuova richiesta di interesse - {label}',
            corpo=(f'Richiesta di informazioni, senza prenotazione.\n\n'
                   f'Ambito: {label}\nNome: {name}\nTelefono: {phone}\n'
                   f'Email: {email or "Non indicata"}\nInformativa privacy: letta.\n'),
            stato='in_preparazione', scade_il=now() + timedelta(days=retention_days),
        )
        db.session.add(record)
        db.session.commit()
        try:
            mail.send(Message(subject=record.oggetto, recipients=[recipient], body=record.corpo))
            record.stato = 'soppressa' if app.config.get('MAIL_SUPPRESS_SEND') else 'inviata'
            record.inviata_il = now()
            db.session.commit()
        except Exception:
            record.stato = 'fallita'
            record.errore = 'Invio SMTP non riuscito.'
            db.session.commit()
            record_event('email', 'errore', 'Richiesta di interesse salvata; email allo studio non inviata.', 'EmailOperativa', record.id)
        return redirect(url_for('showcase.confirmation'), code=303)

    @blueprint.route('/interesse/conferma')
    def confirmation():
        if not showcase_enabled():
            abort(404)
        return render_template('showcase/confirmation.html')

    app.register_blueprint(blueprint)
