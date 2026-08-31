import os
import base64
import json
import re
import secrets
import ssl
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timezone
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash
from googleapiclient.errors import HttpError

# Assicurarsi che l'applicazione possa essere importata
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import app as flask_app
from config import config, normalize_database_url
from app import (
    db,
    limiter,
    Appuntamento,
    Admin,
    Corso,
    IscrizioneCorso,
    PersonaCorso,
    ConsensoPrivacyPaziente,
    PercorsoAccompagnamento,
    IncontroAccompagnamento,
    PresenzaAccompagnamento,
    AutorizzazioneImmagini,
    RegistroEvento,
    EmailOperativa,
    CallSonno,
    QuestionarioSonno,
    crea_amministratore_iniziale,
    inizializza_database,
    valida_configurazione_runtime,
)

@pytest.fixture
def app():
    """Crea e configura una nuova istanza dell'app per ogni test."""
    # Utilizzare la configurazione di test
    flask_app.config.from_object(config['testing'])
    # Stabilire un contesto applicativo
    with flask_app.app_context():
        db.create_all()
        app_module._azzera_stato_calendario()
        yield flask_app
        app_module._azzera_stato_calendario()
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Un client di test per l'app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Un runner di test per i comandi Click dell'app."""
    return app.test_cli_runner()

def test_app_exists(app):
    """Controllo di sanità che l'app esista."""
    assert app is not None

def test_app_is_testing(app):
    """Assicurarsi che l'app sia in modalità di test."""
    assert app.config['TESTING'] == True


def test_timestamp_utc_diventa_ora_italiana_e_distingue_l_ora_ripetuta():
    assert app_module.format_local_timestamp(
        datetime(2026, 8, 26, 18, 46)
    ) == '26/08/2026 20:46 CEST'

    prima_del_salto = app_module.as_local_time(datetime(2026, 3, 29, 0, 30))
    dopo_il_salto = app_module.as_local_time(datetime(2026, 3, 29, 1, 30))
    assert prima_del_salto.strftime('%d/%m/%Y %H:%M %Z') == '29/03/2026 01:30 CET'
    assert dopo_il_salto.strftime('%d/%m/%Y %H:%M %Z') == '29/03/2026 03:30 CEST'

    prima_ora_0230 = app_module.as_local_time(datetime(2026, 10, 25, 0, 30))
    seconda_ora_0230 = app_module.as_local_time(datetime(2026, 10, 25, 1, 30))

    assert prima_ora_0230.strftime('%d/%m/%Y %H:%M %Z') == '25/10/2026 02:30 CEST'
    assert seconda_ora_0230.strftime('%d/%m/%Y %H:%M %Z') == '25/10/2026 02:30 CET'
    assert prima_ora_0230.fold == 0
    assert seconda_ora_0230.fold == 1
    assert prima_ora_0230.astimezone(timezone.utc).replace(tzinfo=None) == datetime(2026, 10, 25, 0, 30)
    assert seconda_ora_0230.astimezone(timezone.utc).replace(tzinfo=None) == datetime(2026, 10, 25, 1, 30)


def test_errore_404_usa_layout_pubblico_e_non_viene_indicizzato(client):
    resp = client.get('/pagina-inesistente')

    assert resp.status_code == 404
    assert resp.text.count('<h1') == 1
    assert 'Pagina non trovata' in resp.text
    assert '<meta name="robots" content="noindex,nofollow">' in resp.text
    assert 'Torna alla homepage' in resp.text


def test_pagina_500_del_modulo_corsi_non_richiede_il_contesto_del_corso(app):
    with app.test_request_context('/iscrizione-corsi/disostruzione-pediatrica'):
        html, status_code = app_module.server_error(RuntimeError('Errore database simulato'))

    assert status_code == 500
    assert 'Non è stato possibile completare la richiesta' in html
    assert 'Torna alla homepage' in html
    assert 'class="sticky-prenota"' not in html


@pytest.mark.parametrize('route', [
    '/conferma',
    '/prenota-call-sonno/conferma',
    '/iscrizione-corsi/conferma',
    '/iscrizione-accompagnamento/conferma',
    '/iscrizione-corsi/interesse/conferma',
])
def test_pagine_di_conferma_hanno_un_h1_e_non_vengono_indicizzate(client, route):
    resp = client.get(route)

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert '<meta name="robots" content="noindex,nofollow">' in resp.text
    assert 'href="/"' in resp.text


def _basic_auth_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return {'Authorization': f'Basic {token}'}


def test_staging_richiede_autenticazione_e_invia_noindex(app, client, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'staging')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_USERNAME', 'tester')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_PASSWORD', 'password-staging-lunga-2026')

    negato = client.get('/')
    autorizzato = client.get(
        '/',
        headers=_basic_auth_header('tester', 'password-staging-lunga-2026'),
    )

    assert negato.status_code == 401
    assert negato.headers['WWW-Authenticate'].startswith('Basic ')
    assert negato.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'
    assert autorizzato.status_code == 200
    assert autorizzato.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'


def test_staging_espone_health_check_e_robots_senza_credenziali(app, client, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'staging')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_USERNAME', 'tester')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_PASSWORD', 'password-staging-lunga-2026')

    health = client.get('/healthz')
    robots = client.get('/robots.txt')

    assert health.status_code == 200
    assert health.get_json() == {'status': 'ok'}
    assert robots.status_code == 200
    assert 'Disallow: /' in robots.text
    assert robots.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'


def test_area_admin_non_viene_memorizzata_ne_indicizzata(app, client, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'production')

    login = client.get('/admin/login')
    accesso_negato = client.get('/admin')
    _login_admin(client)
    admin = client.get('/admin')
    logout = client.get('/admin/logout')

    for response in (login, accesso_negato, admin, logout):
        assert response.headers['Cache-Control'] == 'no-store, private, max-age=0'
        assert response.headers['Pragma'] == 'no-cache'
        assert response.headers['Expires'] == '0'
        assert response.headers['X-Robots-Tag'] == 'noindex, nofollow, noarchive'

    pagina_pubblica = client.get('/')
    assert 'Cache-Control' not in pagina_pubblica.headers
    assert 'X-Robots-Tag' not in pagina_pubblica.headers


def test_health_check_e_esente_dai_limiti_globali(app):
    route_esenti = limiter.limit_manager._route_exemptions

    assert any(route.endswith('.healthz') for route in route_esenti)


def test_rate_limiting_usa_limiti_applicativi_e_non_limiti_predefiniti(app):
    limiti_applicativi = {
        str(limite.limit)
        for limite in limiter.limit_manager.application_limits
    }

    assert limiter.limit_manager.default_limits == []
    assert limiti_applicativi == {'1000 per 1 hour', '10000 per 1 day'}
    assert limiter._headers_enabled is True

    with app.test_request_context('/static/css/base.css'):
        assert app_module._escludi_dal_limite_generale() is True
    with app.test_request_context('/healthz'):
        assert app_module._escludi_dal_limite_generale() is True
    with app.test_request_context('/prenota-call-sonno'):
        assert app_module._escludi_dal_limite_generale() is False


def test_route_miste_limitano_solo_i_post_e_api_orari_resta_limitata_su_get():
    attesi = {
        'richiesta_azienda': '5 per minute',
        'course_interest': '5 per minute',
        'iscrizione_corso': '5 per minute',
        'iscrizione_accompagnamento_privata': '5 per minute',
        'prenota_call_sonno': '5 per hour',
        'questionario_sonno': '10 per hour',
        'prenota': '5 per minute',
        'login': '5 per minute',
        'accetta_proposta_slot': '10 per hour',
        'accetta_invito_lista_attesa': '10 per hour',
    }
    decorati = limiter.limit_manager._decorated_limits

    for endpoint, limite_atteso in attesi.items():
        gruppi = [
            gruppo
            for nome, limiti in decorati.items()
            if nome.endswith(f'.{endpoint}.{endpoint}')
            for gruppo in limiti
        ]
        assert len(gruppi) == 1, endpoint
        assert gruppi[0].limit_provider == limite_atteso
        assert gruppi[0].methods == ('post',)

    limite_api = [
        gruppo
        for nome, limiti in decorati.items()
        if nome.endswith('.api_orari_call_sonno.api_orari_call_sonno')
        for gruppo in limiti
    ]
    assert len(limite_api) == 1
    assert limite_api[0].limit_provider == '30 per minute'
    assert limite_api[0].methods is None


def test_flask_limiter_non_consuma_il_limite_specifico_con_i_get():
    probe = Flask('rate-limit-methods')
    probe.config['TESTING'] = True
    probe_limiter = Limiter(
        get_remote_address,
        app=probe,
        application_limits=['100 per hour'],
        headers_enabled=True,
        storage_uri='memory://',
    )

    @probe.route('/mista', methods=['GET', 'POST'])
    @probe_limiter.limit('2 per hour', methods=['POST'])
    def route_mista_probe():
        return 'ok'

    client = probe.test_client()
    risposte_get = [client.get('/mista') for _ in range(10)]
    risposte_post = [client.post('/mista') for _ in range(3)]

    assert all(risposta.status_code == 200 for risposta in risposte_get)
    assert [risposta.status_code for risposta in risposte_post] == [200, 200, 429]
    assert risposte_post[-1].headers.get('Retry-After')


def test_flask_limiter_aggrega_endpoint_dinamici_ed_esclude_statici():
    probe = Flask('rate-limit-application')
    probe.config['TESTING'] = True
    Limiter(
        get_remote_address,
        app=probe,
        application_limits=['2 per hour'],
        application_limits_exempt_when=lambda: app_module.request.endpoint == 'static',
        storage_uri='memory://',
    )

    @probe.get('/prima')
    def prima_probe():
        return 'prima'

    @probe.get('/seconda')
    def seconda_probe():
        return 'seconda'

    client = probe.test_client()

    assert client.get('/prima').status_code == 200
    assert client.get('/seconda').status_code == 200
    assert client.get('/prima').status_code == 429
    assert [
        client.get('/static/inesistente.css').status_code
        for _ in range(3)
    ] == [404, 404, 404]


def test_risposta_429_e_in_italiano_e_non_registra_dati_personali(app, caplog):
    errore = type('ErroreLimite', (), {'description': '5 per 1 minute'})()

    with app.test_request_context('/admin/login', method='POST'), caplog.at_level('WARNING'):
        html, status = app_module.troppe_richieste(errore)

    assert status == 429
    assert 'Troppe richieste' in html
    assert 'Attendi e riprova più tardi.' in html
    assert 'endpoint=login metodo=POST limite=5 per 1 minute' in caplog.text
    assert '127.0.0.1' not in caplog.text

    with app.test_request_context('/api/orari-call-sonno/2099-01-05'):
        risposta, status = app_module.troppe_richieste(errore)

    assert status == 429
    assert risposta.get_json() == {
        'errore': 'Hai effettuato troppe richieste in poco tempo. Attendi e riprova più tardi.'
    }


def test_staging_non_si_avvia_senza_protezione(app, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'staging')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_USERNAME', None)
    monkeypatch.setitem(app.config, 'STAGING_AUTH_PASSWORD', None)

    with app.app_context(), pytest.raises(RuntimeError, match='Lo staging richiede'):
        inizializza_database()


def _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='staging'):
    monkeypatch.setattr(app_module, 'config_name', 'production')
    monkeypatch.setitem(app.config, 'APP_ENV', ambiente)
    monkeypatch.setitem(app.config, 'SECRET_KEY', 's' * 32)
    monkeypatch.setitem(app.config, 'SECRET_KEY_IS_EPHEMERAL', False)
    monkeypatch.setitem(app.config, 'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg://db/test')
    monkeypatch.setitem(app.config, 'DATABASE_URL_IS_EXPLICIT', True)
    monkeypatch.setitem(app.config, 'STAGING_AUTH_USERNAME', 'tester')
    monkeypatch.setitem(app.config, 'STAGING_AUTH_PASSWORD', 'password-staging-lunga-2026')
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_PASSWORD', 'password-admin-lunga-2026')
    monkeypatch.setitem(app.config, 'MAIL_USE_TLS', True)
    monkeypatch.setitem(app.config, 'MAIL_USE_SSL', False)
    monkeypatch.setitem(app.config, 'MAIL_SUPPRESS_SEND', ambiente == 'staging')
    monkeypatch.setitem(app.config, 'STAGING_LIVE_INTEGRATIONS', False)
    monkeypatch.setitem(
        app.config,
        'PUBLIC_BASE_URL',
        'https://scstudioinfermieristico.it' if ambiente == 'production' else None,
    )


def test_validazione_staging_accetta_solo_configurazione_sicura(app, monkeypatch):
    _configura_runtime_esterno_sicuro(app, monkeypatch)

    valida_configurazione_runtime()


def test_validazione_staging_rifiuta_secret_key_effimera(app, monkeypatch):
    _configura_runtime_esterno_sicuro(app, monkeypatch)
    monkeypatch.setitem(app.config, 'SECRET_KEY_IS_EPHEMERAL', True)

    with pytest.raises(RuntimeError, match='SECRET_KEY stabile'):
        valida_configurazione_runtime()


def test_validazione_produzione_richiede_email_e_calendar(app, monkeypatch):
    _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='production')
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', None)
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', None)

    with pytest.raises(RuntimeError, match='MAIL_USERNAME.*GOOGLE_CALENDAR_ID'):
        valida_configurazione_runtime()


def test_validazione_produzione_completa(app, monkeypatch, tmp_path):
    _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='production')
    service_account_file = tmp_path / 'google-service-account.json'
    service_account_file.write_text('{}')
    monkeypatch.setitem(app.config, 'MAIL_SERVER', 'smtp.mail.ovh.net')
    monkeypatch.setitem(app.config, 'MAIL_PORT', 587)
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@scstudioinfermieristico.it')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(
        app.config,
        'MAIL_DEFAULT_SENDER',
        'S.C. Studio Infermieristico <info@scstudioinfermieristico.it>',
    )
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')

    valida_configurazione_runtime()


def test_validazione_produzione_non_accetta_fallback_smtp(app, monkeypatch, tmp_path):
    _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='production')
    service_account_file = tmp_path / 'google-service-account.json'
    service_account_file.write_text('{}')
    monkeypatch.setitem(app.config, 'MAIL_SERVER', 'smtp.gmail.com')
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@scstudioinfermieristico.it')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(
        app.config,
        'MAIL_DEFAULT_SENDER',
        'S.C. Studio Infermieristico <info@scstudioinfermieristico.it>',
    )
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')

    with pytest.raises(RuntimeError, match='smtp.mail.ovh.net'):
        valida_configurazione_runtime()


def test_validazione_produzione_rifiuta_mittente_diverso_da_zimbra(app, monkeypatch, tmp_path):
    _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='production')
    service_account_file = tmp_path / 'google-service-account.json'
    service_account_file.write_text('{}')
    monkeypatch.setitem(app.config, 'MAIL_SERVER', 'smtp.mail.ovh.net')
    monkeypatch.setitem(app.config, 'MAIL_PORT', 587)
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@scstudioinfermieristico.it')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(app.config, 'MAIL_DEFAULT_SENDER', 'Studio <altro@example.invalid>')
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')

    with pytest.raises(RuntimeError, match='MAIL_DEFAULT_SENDER'):
        valida_configurazione_runtime()


def test_preproduzione_privata_ammette_integrazioni_reali(app, monkeypatch, tmp_path):
    _configura_runtime_esterno_sicuro(app, monkeypatch)
    service_account_file = tmp_path / 'google-service-account.json'
    service_account_file.write_text('{}')
    monkeypatch.setitem(app.config, 'STAGING_LIVE_INTEGRATIONS', True)
    monkeypatch.setitem(app.config, 'MAIL_SUPPRESS_SEND', False)
    monkeypatch.setitem(app.config, 'MAIL_SERVER', 'smtp.mail.ovh.net')
    monkeypatch.setitem(app.config, 'MAIL_PORT', 587)
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@scstudioinfermieristico.it')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(
        app.config,
        'MAIL_DEFAULT_SENDER',
        'S.C. Studio Infermieristico <info@scstudioinfermieristico.it>',
    )
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')

    valida_configurazione_runtime()


def test_staging_gratuito_non_puo_inviare_email_reali(app, monkeypatch):
    _configura_runtime_esterno_sicuro(app, monkeypatch)
    monkeypatch.setitem(app.config, 'MAIL_SUPPRESS_SEND', False)

    with pytest.raises(RuntimeError, match='staging gratuito'):
        valida_configurazione_runtime()


def test_produzione_richiede_origine_pubblica_https(app, monkeypatch, tmp_path):
    _configura_runtime_esterno_sicuro(app, monkeypatch, ambiente='production')
    service_account_file = tmp_path / 'google-service-account.json'
    service_account_file.write_text('{}')
    monkeypatch.setitem(app.config, 'MAIL_SERVER', 'smtp.mail.ovh.net')
    monkeypatch.setitem(app.config, 'MAIL_PORT', 587)
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@scstudioinfermieristico.it')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(
        app.config,
        'MAIL_DEFAULT_SENDER',
        'S.C. Studio Infermieristico <info@scstudioinfermieristico.it>',
    )
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(app.config, 'PUBLIC_BASE_URL', 'https://example.invalid/percorso')

    with pytest.raises(RuntimeError, match='origine HTTPS senza percorso'):
        valida_configurazione_runtime()


def test_database_url_postgres_compatibile_con_psycopg():
    assert normalize_database_url('postgres://user:pass@host/db').startswith('postgresql+psycopg://')
    assert normalize_database_url('postgresql://user:pass@host/db').startswith('postgresql+psycopg://')


def test_database_empty(app):
    """Iniziare con un database vuoto."""
    with app.app_context():
        assert Appuntamento.query.count() == 0
        assert Admin.query.count() == 0
        assert Corso.query.count() == 0
        assert IscrizioneCorso.query.count() == 0
        assert PersonaCorso.query.count() == 0
        assert PercorsoAccompagnamento.query.count() == 0
        assert IncontroAccompagnamento.query.count() == 0
        assert PresenzaAccompagnamento.query.count() == 0
        assert RegistroEvento.query.count() == 0
        assert CallSonno.query.count() == 0
        assert QuestionarioSonno.query.count() == 0
        assert ConsensoPrivacyPaziente.query.count() == 0


def _csrf_call_sonno(client):
    response = client.get('/prenota-call-sonno')
    return re.search(r'name="_csrf_token" value="([^"]+)"', response.text).group(1)


def _dati_call_sonno(client, data=None, ora='09:00'):
    data = data or app_module.prima_data_call_disponibile().isoformat()
    return {
        'nome': 'Anna Verdi',
        'telefono': '333 1234567',
        'email': 'anna@example.com',
        'eta_bambino_mesi': '18',
        'ruolo_richiedente': 'Genitore con responsabilità genitoriale',
        'difficolta_principale': 'Risvegli notturni frequenti',
        'durata_difficolta': 'Da 1 a 3 mesi',
        'obiettivo_call': 'Capire quale percorso è adatto alla nostra situazione.',
        'data': data,
        'ora': ora,
        'presa_visione_offerta': 'on',
        'conferma_ambito': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': _csrf_call_sonno(client),
    }


def test_prenotazione_call_sonno_blocca_subito_lo_slot(client):
    dati = _dati_call_sonno(client)
    with patch.object(app_module, 'crea_o_aggiorna_evento_calendario_call_sonno', return_value=True):
        response = client.post('/prenota-call-sonno', data=dati, follow_redirects=True)

    assert response.status_code == 200
    assert 'Lo slot è riservato provvisoriamente' in response.text
    assert 'La call non è ancora confermata' in response.text
    with flask_app.app_context():
        call = CallSonno.query.one()
        assert call.stato == 'In attesa'
        assert call.consenso_privacy is True
        assert call.presa_visione_offerta is True
        assert call.conferma_ambito is True
        assert call.ruolo_richiedente == 'Genitore con responsabilità genitoriale'
        assert call.eta_bambino_mesi == 18

    availability = client.get(f'/api/orari-call-sonno/{dati["data"]}').get_json()
    assert '09:00' in availability['occupati']


def test_errori_email_e_calendar_non_perdono_la_call_sonno(client):
    dati = _dati_call_sonno(client)

    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('servizio non disponibile')):
        response = client.post('/prenota-call-sonno', data=dati)

    assert response.status_code == 302
    with flask_app.app_context():
        call = CallSonno.query.one()
        assert call.stato == 'In attesa'
        eventi = RegistroEvento.query.filter_by(entita_tipo='CallSonno', entita_id=call.id).all()
        assert {evento.categoria for evento in eventi} == {'email', 'google_calendar'}
        assert sum(evento.categoria == 'email' for evento in eventi) == 2
        assert all(evento.esito in {'errore', 'avviso'} for evento in eventi)


def test_call_sonno_dura_20_minuti_e_blocca_30_minuti_in_agenda(app):
    data = app_module.prima_data_call_disponibile().isoformat()
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True, data=data, ora='09:00', stato='In attesa',
        )
        db.session.add(call)
        db.session.commit()

        corpo_evento = app_module._corpo_evento_da_call_sonno(call)
        inizio = datetime.fromisoformat(corpo_evento['start']['dateTime'])
        fine = datetime.fromisoformat(corpo_evento['end']['dateTime'])

        assert app_module.DURATA_CALL_SONNO_MINUTI == 20
        assert app_module.BLOCCO_CALL_SONNO_MINUTI == 30
        assert fine - inizio == app_module.timedelta(minutes=30)
        assert app_module.slot_occupato_db(data, '09:20', 10) is True
        assert app_module.slot_occupato_db(data, '09:30', 10) is False
        assert '09:20' not in app_module.ORARI_CALL_SONNO
        assert '09:30' in app_module.ORARI_CALL_SONNO


def test_call_sonno_prenotabile_anche_il_sabato(app):
    giorno = app_module.prima_data_call_disponibile()
    while giorno.weekday() != 5 or app_module.is_festivo(giorno):
        giorno += app_module.timedelta(days=1)

    assert app_module.orario_call_prenotabile(giorno.isoformat(), '09:00') is True


def test_prenotazione_call_sonno_salva_utm(client):
    dati = _dati_call_sonno(client)
    dati.update({
        'utm_source': 'instagram',
        'utm_medium': 'paid_social',
        'utm_campaign': 'sonno_settembre',
        'utm_content': 'risvegli_video_1',
    })
    with patch.object(app_module, 'crea_o_aggiorna_evento_calendario_call_sonno', return_value=True):
        response = client.post('/prenota-call-sonno', data=dati)

    assert response.status_code == 302
    with flask_app.app_context():
        call = CallSonno.query.one()
        assert call.utm_source == 'instagram'
        assert call.utm_content == 'risvegli_video_1'


def test_pagina_sonno_mostra_formule_e_prezzi_prima_della_prenotazione(client):
    landing = client.get('/consulenze-online')
    booking = client.get('/prenota-call-sonno')

    assert 'Consulenza mirata' in landing.text
    assert 'Percorso sonno personalizzato' in landing.text
    assert 'Percorso sonno con affiancamento' in landing.text
    assert '200 €' in landing.text
    assert '320 €' in landing.text
    assert 'partono da <strong>75 €</strong>' in booking.text
    assert 'percorso personalizzato 200 €' in booking.text
    assert 'name="eta_bambino_mesi"' in booking.text
    assert 'max="12"' not in booking.text
    assert '0-12' not in landing.text
    assert '0–12' not in landing.text


def test_obiettivo_call_sonno_e_facoltativo(client):
    dati = _dati_call_sonno(client)
    dati.pop('obiettivo_call')

    with patch.object(app_module, 'crea_o_aggiorna_evento_calendario_call_sonno', return_value=True):
        response = client.post('/prenota-call-sonno', data=dati)

    assert response.status_code == 302
    with flask_app.app_context():
        assert CallSonno.query.one().obiettivo_call is None


def test_condizioni_sonno_pubblicano_versione_prezzi_e_rimborsi(client):
    response = client.get('/condizioni-consulenza-sonno')

    assert response.status_code == 200
    assert response.text.count('<h1') == 1
    assert '31 agosto 2026' in response.text
    assert 'Consulenza mirata: 75 €' in response.text
    assert 'Percorso sonno personalizzato: 200 €' in response.text
    assert 'Percorso sonno con affiancamento: 320 €' in response.text
    assert 'rimborso di 150 €' in response.text
    assert 'dal giorno 46 al giorno 60' in response.text
    assert '75 giorni dalla data di invio del questionario compilato' in response.text


def test_checkbox_call_sonno_usano_stile_compatto_mobile(client):
    booking = client.get('/prenota-call-sonno')

    assert booking.status_code == 200
    assert booking.text.count('class="privacy-checkbox"') == 3


def test_promemoria_call_sonno_email_non_si_duplica(app):
    adesso = datetime(2026, 9, 20, 10, 0, tzinfo=app_module.FUSO_ORARIO)
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True,
            data='2026-09-21', ora='09:00', stato='Confermata',
        )
        db.session.add(call)
        db.session.commit()

        with patch.object(
            app_module, 'invia_email_promemoria_call_sonno', return_value=True
        ) as email:
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)

        db.session.refresh(call)
        assert call.promemoria_email_24h_il is not None
        email.assert_called_once_with(call, 24)


def test_promemoria_call_sonno_email_due_ore(app):
    adesso = datetime(2026, 9, 21, 7, 30, tzinfo=app_module.FUSO_ORARIO)
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True,
            data='2026-09-21', ora='09:00', stato='Confermata',
        )
        db.session.add(call)
        db.session.commit()

        with patch.object(
            app_module, 'invia_email_promemoria_call_sonno', return_value=True
        ) as email:
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)

        db.session.refresh(call)
        assert call.promemoria_email_2h_il is not None
        email.assert_called_once_with(call, 2)


def test_call_sonno_non_si_sovrappone_a_prestazione(client):
    data = app_module.prima_data_call_disponibile().isoformat()
    with flask_app.app_context():
        db.session.add(Appuntamento(
            nome='Paziente', telefono='3331234567', email='p@example.com',
            servizio='Medicazione semplice', data=data, ora='09:00', stato='Confermato',
        ))
        db.session.commit()

    response = client.post('/prenota-call-sonno', data=_dati_call_sonno(client, data, '09:00'))
    assert 'Questo orario non è più disponibile' in response.text
    with flask_app.app_context():
        assert CallSonno.query.count() == 0


def test_questionario_sonno_disponibile_solo_dopo_invito(client):
    with flask_app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True, data='2026-09-21', ora='09:00', stato='Conclusa',
            formula_scelta='percorso', token_questionario=secrets.token_urlsafe(48),
            pagamento_confermato_il=app_module.utc_now(),
        )
        db.session.add(call)
        db.session.commit()
        token = call.token_questionario

    response = client.get(f'/questionario-sonno/{token}')
    assert response.status_code == 200
    assert 'noindex,nofollow,noarchive' in response.text
    assert 'name="data_nascita"' in response.text
    assert 'name="eta_corretta"' in response.text
    csrf = re.search(r'name="_csrf_token" value="([^"]+)"', response.text).group(1)
    payload = {
        '_csrf_token': csrf,
        'nome_bambino': 'Leo',
        'data_nascita': '2026-02-01',
        'alimentazione': 'Mista',
        'dove_dorme': 'Lettino in camera dei genitori',
        'durata_difficolta': 'Da alcune settimane',
        'cambiamento_desiderato': 'Ridurre i risvegli più lunghi',
        'consenso_dati_sanitari': 'on',
    }
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        completed = client.post(f'/questionario-sonno/{token}', data=payload, follow_redirects=True)
    assert 'Questionario ricevuto' in completed.text
    with flask_app.app_context():
        assert QuestionarioSonno.query.count() == 1
        call_id = CallSonno.query.one().id
        attivita = app_module.AttivitaAdmin.query.filter_by(
            entita_tipo='CallSonno', entita_id=call_id, stato='Aperta',
        ).one()
        assert attivita.titolo == 'Leggere il questionario di Anna Verdi'
        email = EmailOperativa.query.filter_by(entita_tipo='CallSonno', entita_id=call_id).one()
        assert email.oggetto == 'Questionario sonno compilato - Anna Verdi'
        assert email.stato == 'fallita'
        assert RegistroEvento.query.filter_by(
            categoria='email', entita_tipo='CallSonno', entita_id=call_id,
        ).one().esito == 'errore'

    protected = client.get(f'/admin/call-sonno/{call_id}/questionario')
    assert protected.status_code == 302
    _login_admin(client)
    admin_view = client.get(f'/admin/call-sonno/{call_id}/questionario')
    assert admin_view.status_code == 200
    assert 'Questionario sonno di Anna Verdi' in admin_view.text
    assert 'Ridurre i risvegli più lunghi' in admin_view.text
    detail = client.get(f'/admin/pratica/CallSonno/{call_id}')
    assert 'Leggi questionario' in detail.text

def test_create_admin(app):
    """Testare che un amministratore possa essere creato."""
    with app.app_context():
        admin = Admin(username='testadmin', password='hashed')
        db.session.add(admin)
        db.session.commit()
        assert Admin.query.filter_by(username='testadmin').first() is not None


def test_database_vuoto_non_crea_admin_predefinito(app):
    with app.app_context():
        inizializza_database()

        assert Admin.query.count() == 0


def test_bootstrap_admin_richiede_credenziali_esplicite_e_salva_hash(app, monkeypatch):
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_USERNAME', 'selene-admin')
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_PASSWORD', 'frase-segreta-lunga-2026')

    with app.app_context():
        inizializza_database()
        admin = Admin.query.one()

        assert admin.username == 'selene-admin'
        assert admin.password != 'frase-segreta-lunga-2026'
        assert check_password_hash(admin.password, 'frase-segreta-lunga-2026')


def test_bootstrap_admin_rifiuta_password_corta(app):
    with app.app_context(), pytest.raises(ValueError, match='almeno 16 caratteri'):
        crea_amministratore_iniziale('selene-admin', 'troppo-corta')


def test_bootstrap_admin_richiede_entrambe_le_variabili(app, monkeypatch):
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_USERNAME', 'selene-admin')
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_PASSWORD', None)

    with app.app_context(), pytest.raises(RuntimeError, match='Configurare insieme'):
        inizializza_database()


def test_produzione_rifiuta_database_senza_admin(app, monkeypatch):
    monkeypatch.setattr(app_module, 'config_name', 'production')
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_USERNAME', None)
    monkeypatch.setitem(app.config, 'ADMIN_BOOTSTRAP_PASSWORD', None)

    with app.app_context(), pytest.raises(RuntimeError, match='Database senza amministratore'):
        inizializza_database()


def test_produzione_rifiuta_credenziale_legacy(app, monkeypatch):
    with app.app_context():
        db.session.add(Admin(
            username='admin',
            password=generate_password_hash('cambiami123'),
        ))
        db.session.commit()

    monkeypatch.setattr(app_module, 'config_name', 'production')
    with app.app_context(), pytest.raises(RuntimeError, match='legacy'):
        inizializza_database()


def test_comando_create_admin_crea_un_account_sicuro(app, runner):
    result = runner.invoke(
        args=['create-admin'],
        input='selene-admin\nfrase-segreta-lunga-2026\nfrase-segreta-lunga-2026\n',
    )

    assert result.exit_code == 0
    with app.app_context():
        admin = Admin.query.one()
        assert admin.username == 'selene-admin'
        assert check_password_hash(admin.password, 'frase-segreta-lunga-2026')

def test_create_appointment(app):
    """Testare la creazione di un appuntamento."""
    with app.app_context():
        appt = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Iniezione intramuscolare',
            data='2026-07-01',
            ora='10:00',
            note='Nessuna'
        )
        db.session.add(appt)
        db.session.commit()
        saved = Appuntamento.query.filter_by(email='mario@example.com').first()
        assert saved is not None
        assert saved.nome == 'Mario Rossi'
        assert saved.stato == 'In attesa'  # predefinito

def test_orari_occupati_endpoint(client):
    """Testare l'endpoint /api/orari-occupati/<data>."""
    with flask_app.app_context():
        # Inserire un appuntamento per una data specifica
        appt = Appuntamento(
            nome='Test User',
            telefono='123',
            email='test@test.com',
            servizio='Test',
            data='2026-07-10',
            ora='10:30',
            stato='Confermato'
        )
        db.session.add(appt)
        db.session.commit()
        # Richiedere l'endpoint
        resp = client.get('/api/orari-occupati/2026-07-10')
        assert resp.status_code == 200
        data = resp.get_json()
        assert '10:30' in data
        # Assicurarsi che gli appuntamenti annullati non siano inclusi
        appt.stato = 'Annullato'
        db.session.commit()
        resp2 = client.get('/api/orari-occupati/2026-07-10')
        data2 = resp2.get_json()
        assert '10:30' not in data2  # dovrebbe essere libero dopo la cancellazione

def test_holiday_flow(client):
    """Semplice test della home page."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'S.C. Studio Infermieristico' in resp.data  # adeguare in base al contenuto effettivo
    assert 'data-site-header' in resp.text
    assert 'aria-label="Navigazione principale"' in resp.text
    assert 'aria-label="Torna alla homepage"' in resp.text
    assert 'href="/faq"' in resp.text
    assert 'aria-label="Prestazioni infermieristiche"' in resp.text


def test_header_elenca_tutte_le_tipologie_di_corso(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert resp.text.count('href="/iscrizione-corsi/laboratorio-infanzia"') == 3
    assert 'Laboratori, gioco e sviluppo' in resp.text
    assert 'Laboratori alimentari, gioco e sviluppo' in resp.text


def test_header_mette_in_evidenza_il_quiz_di_orientamento(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert 'site-nav__link site-nav__link--guide' in resp.text
    assert 'data-conversion="header_quiz_orientamento"' in resp.text
    assert 'class="mobile-nav__guide' in resp.text
    assert 'Quiz di orientamento' in resp.text
    assert 'Tre domande per trovare il percorso più adatto.' in resp.text


def test_comportamento_javascript_header():
    project_root = Path(app_module.__file__).resolve().parent
    test_file = project_root / 'tests' / 'js' / 'menu-mobile.test.js'
    result = subprocess.run(
        ['node', '--test', str(test_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('route', ['/', '/chi-sono', '/faq', '/iscrizione-corsi', '/consulenze-online', '/prenota-call-sonno'])
def test_widget_whatsapp_globale_assente(client, route):
    resp = client.get(route)

    assert resp.status_code == 200
    assert 'class="whatsapp-widget"' not in resp.text
    assert 'data-conversion="whatsapp_floating_' not in resp.text


@pytest.mark.parametrize(
    'route',
    [
        '/prestazioni-infermieristiche',
        '/prenota',
        '/iscrizione-corsi/disostruzione-pediatrica',
        '/admin/login',
    ],
)
def test_widget_whatsapp_assente_dai_flussi_specifici(client, route):
    resp = client.get(route)

    assert resp.status_code == 200
    assert 'class="whatsapp-widget"' not in resp.text


def test_whatsapp_resta_disponibile_solo_nelle_cta_contestuali(client):
    faq = client.get('/faq')
    sonno = client.get('/consulenze-online')

    assert 'data-conversion="faq_whatsapp"' in faq.text
    assert 'data-conversion="sleep_hero_whatsapp"' in sonno.text


@pytest.mark.parametrize(
    'route',
    [
        '/admin/aggiorna/1/Confermato',
        '/admin/corso/elimina/1',
        '/admin/iscrizione-corso/1/Confermato',
    ],
)
def test_azioni_admin_mutative_rifiutano_get(client, route):
    assert client.get(route).status_code == 405


def test_css_core_e_modulo_homepage(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert 'css/fonts.css' in resp.text
    assert 'css/tokens.css' in resp.text
    assert 'css/base.css' in resp.text
    assert 'css/components.css' in resp.text
    assert 'css/homepage.css' in resp.text
    assert 'js/home-scroll-motion.js' in resp.text
    assert 'css/consulenza.css' not in resp.text
    assert 'css/admin.css' not in resp.text
    assert 'css/stile.css' not in resp.text


def test_font_sono_self_hosted_e_csp_non_ammette_google_fonts(client):
    homepage = client.get('/')
    login = client.get('/admin/login')
    fonts_css = client.get('/static/css/fonts.css')

    for resp in (homepage, login):
        assert resp.status_code == 200
        assert 'css/fonts.css' in resp.text
        assert 'fonts.googleapis.com' not in resp.text
        assert 'fonts.gstatic.com' not in resp.text

        csp = resp.headers['Content-Security-Policy']
        assert "font-src 'self'" in csp
        assert 'fonts.googleapis.com' not in csp
        assert 'fonts.gstatic.com' not in csp

    assert fonts_css.status_code == 200
    assert fonts_css.text.count('@font-face') == 6
    assert "font-family: 'Atkinson Hyperlegible'" in fonts_css.text
    assert "font-family: 'Bricolage Grotesque'" in fonts_css.text
    assert 'font-display: swap' in fonts_css.text

    assert 'AtkinsonHyperlegible-Regular.woff2' in homepage.text
    assert 'BricolageGrotesque-ExtraBold.woff2' in homepage.text
    assert 'AtkinsonHyperlegible-Regular.woff2' in login.text
    assert 'BricolageGrotesque-Bold.woff2' in login.text
    assert 'BricolageGrotesque-ExtraBold.woff2' not in login.text

    font_paths = [
        '/static/fonts/atkinson-hyperlegible/AtkinsonHyperlegible-Regular.woff2',
        '/static/fonts/atkinson-hyperlegible/AtkinsonHyperlegible-Bold.woff2',
        '/static/fonts/bricolage-grotesque/BricolageGrotesque-Medium.woff2',
        '/static/fonts/bricolage-grotesque/BricolageGrotesque-SemiBold.woff2',
        '/static/fonts/bricolage-grotesque/BricolageGrotesque-Bold.woff2',
        '/static/fonts/bricolage-grotesque/BricolageGrotesque-ExtraBold.woff2',
    ]
    for font_path in font_paths:
        font_response = client.get(font_path)
        assert font_response.status_code == 200
        assert font_response.mimetype == 'font/woff2'


def test_privacy_policy_pubblica_il_testo_aggiornato(client):
    response = client.get('/privacy')

    assert response.status_code == 200
    assert 'Informativa sul trattamento dei dati personali' in response.text
    assert 'Ultimo aggiornamento: 29 agosto 2026' in response.text
    assert response.text.count('class="privacy-blocco') == 21
    assert 'Selene Campetta, titolare di S.C. Studio Infermieristico' in response.text
    assert 'P. IVA 02439230687' in response.text
    assert 'art. 9, par. 2, lett. h) GDPR' in response.text
    assert 'non è pertanto richiesto il consenso dell’interessato' in response.text
    assert 'data presunta del parto' in response.text
    assert 'settimana di gravidanza attuale' in response.text
    assert 'massimo <strong>6 mesi</strong>' in response.text
    assert 'massimo <strong>12 mesi</strong>' in response.text
    assert 'di regola massimo <strong>24 mesi</strong>' in response.text
    assert 'Render, Zimbra, Google, ArzaMed, PayPal, Meta/WhatsApp, Meta Pixel e Behold' in response.text
    assert 'il loro caricamento non richiede una connessione a Google Fonts' in response.text
    assert 'richieste di revoca' in response.text
    assert 'mailto:info@scstudioinfermieristico.it' in response.text
    assert 'Erogazione della prestazione sanitaria:</strong> necessaria' not in response.text
    assert 'Ultimo aggiornamento:</strong> Luglio 2026' not in response.text


def test_checkbox_obbligatorie_distinguono_presa_visione_e_consensi_specifici(client):
    prenotazione = client.get('/prenota')
    call = client.get('/prenota-call-sonno')
    corso = client.get('/iscrizione-corsi/disostruzione-pediatrica')
    nascita = client.get('/iscrizione-corsi/accompagnamento-nascita')
    blsd = client.get('/iscrizione-corsi/blsd')
    laboratorio = client.get('/iscrizione-corsi/laboratorio-infanzia')
    interesse = client.get('/iscrizione-corsi/interesse')

    assert 'Dichiaro di aver letto' in prenotazione.text
    assert 'Dichiaro di aver letto' in call.text
    assert 'Dichiaro di aver letto' in corso.text
    for modulo_corso in [corso, nascita, blsd, laboratorio]:
        assert modulo_corso.text.count('name="condizioni_corso" required') == 1
        assert 'Dichiaro di aver letto e accettato le' in modulo_corso.text
        assert 'href="/condizioni-iscrizione-corsi"' in modulo_corso.text
    assert 'name="condizioni_corso"' not in interesse.text
    assert 'name="condizioni_corso"' not in call.text
    assert 'name="condizioni_corso"' not in prenotazione.text
    assert 'name="consenso_immagini"' not in corso.text
    assert 'name="consenso_dati_gravidanza" required' in nascita.text
    assert 'Acconsento esplicitamente' in nascita.text


def test_condizioni_iscrizione_corsi_pubblica_testo_integrale(client):
    response = client.get('/condizioni-iscrizione-corsi')

    assert response.status_code == 200
    assert response.text.count('<h1>') == 1
    assert '<h1>Condizioni di iscrizione ai corsi</h1>' in response.text
    assert 'pagamento è previsto in presenza il giorno dell’attività' in response.text
    assert 'L’invio del modulo online costituisce una richiesta di iscrizione' in response.text
    assert 'Non è richiesto alcun pagamento anticipato' in response.text
    assert 'senza costi e senza penali' in response.text
    assert 'di richiedere il pagamento anticipato della quota di partecipazione' in response.text
    assert 'La richiesta di spostamento non comporta automaticamente la prenotazione' in response.text
    assert 'in caso di annullamento precedente allo svolgimento non vi sono somme anticipate da rimborsare' in response.text
    assert 'Tali indicazioni costituiscono parte integrante delle condizioni di partecipazione' in response.text


def test_scheda_iscrizione_registra_revoca_immagini_e_informativa_in_presenza(client):
    with flask_app.app_context():
        iscrizione = IscrizioneCorso(
            corso_tipo='laboratorio-infanzia',
            corso_titolo='Laboratorio infanzia',
            nome='Genitore Test',
            telefono='3331234567',
            email='genitore@example.com',
            codice_fiscale='TSTGTR80A01G482X',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
        )
        db.session.add(iscrizione)
        db.session.commit()
        iscrizione_id = iscrizione.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/iscrizione-corso/{iscrizione_id}/autorizzazione-immagini',
        data={
            '_csrf_token': csrf,
            'soggetto_nome': 'Bambino Test',
            'soggetto_tipo': 'Minore',
            'finalita_didattica': 'on',
            'canale_materiali': 'on',
            'primo_genitore_nome': 'Genitore Uno',
            'secondo_genitore_nome': 'Genitore Due',
        },
    )
    assert response.status_code == 302

    response = client.post(
        f'/admin/iscrizione-corso/{iscrizione_id}/informativa-terzo',
        data={'_csrf_token': csrf, 'destinatario': 'Secondo Partecipante'},
    )
    assert response.status_code == 302

    with flask_app.app_context():
        autorizzazione = AutorizzazioneImmagini.query.one()
        assert autorizzazione.secondo_genitore_nome == 'Genitore Due'
        assert autorizzazione.versione_informativa == '2026-08-29'
        autorizzazione_id = autorizzazione.id
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.informativa_terzi_destinatario == 'Secondo Partecipante'
        assert iscrizione.informativa_terzi_consegnata_il is not None

    response = client.post(
        f'/admin/autorizzazione-immagini/{autorizzazione_id}/revoca',
        data={'_csrf_token': csrf},
    )
    assert response.status_code == 302
    with flask_app.app_context():
        assert db.session.get(AutorizzazioneImmagini, autorizzazione_id).revocato_il is not None


def test_conservazione_privacy_anonimizza_dati_scaduti_e_mantiene_riepiloghi(client):
    riferimento = datetime(2026, 8, 29, 12, 0, 0)
    with flask_app.app_context():
        persona = PersonaCorso(
            nome='Persona Scaduta',
            telefono='3331234567',
            email='persona@example.com',
            aggiornato_il=datetime(2024, 1, 1),
        )
        corso = Corso(
            titolo='Corso storico',
            tipo='bls-d',
            data='2025-01-01',
            stato='Concluso',
        )
        appuntamento = Appuntamento(
            nome='Paziente Scaduto',
            telefono='3331234567',
            email='paziente@example.com',
            servizio='Medicazione semplice',
            data='2024-01-01',
            ora='10:00',
            stato='Concluso',
        )
        call = CallSonno(
            nome='Famiglia Scaduta',
            telefono='3331234567',
            email='famiglia@example.com',
            eta_bambino_mesi=6,
            difficolta_principale='Risvegli',
            data='2025-01-01',
            ora='10:00',
            stato='Conclusa',
            aggiornato_il=datetime(2025, 1, 1),
        )
        iscrizione = IscrizioneCorso(
            corso=corso,
            persona=persona,
            corso_tipo='bls-d',
            corso_titolo='Corso storico',
            nome='Persona Scaduta',
            telefono='3331234567',
            email='persona@example.com',
            codice_fiscale='TSTPRS80A01G482X',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            stato='Confermato',
            dati_extra=json.dumps({'dato': 'personale'}),
        )
        db.session.add_all([persona, corso, appuntamento, call, iscrizione])
        db.session.flush()
        db.session.add(QuestionarioSonno(
            call_sonno=call,
            risposte=json.dumps({'condizioni_note': 'dato sanitario'}),
            consenso_dati_sanitari=True,
        ))
        db.session.commit()
        ids = {
            'persona': persona.id,
            'corso': corso.id,
            'appuntamento': appuntamento.id,
            'call': call.id,
            'iscrizione': iscrizione.id,
        }

        conteggi = app_module.applica_conservazione_privacy(riferimento)

        assert conteggi == {
            'appuntamenti': 1,
            'call_sonno': 1,
            'iscrizioni_corso': 1,
            'persone': 1,
        }
        assert db.session.get(Appuntamento, ids['appuntamento']).nome == '[dati anonimizzati]'
        assert db.session.get(CallSonno, ids['call']).nome == '[dati anonimizzati]'
        assert db.session.get(IscrizioneCorso, ids['iscrizione']).nome == '[dati anonimizzati]'
        assert db.session.get(IscrizioneCorso, ids['iscrizione']).posti == 1
        assert db.session.get(Corso, ids['corso']).titolo == 'Corso storico'
        assert db.session.get(PersonaCorso, ids['persona']).nome == '[dati anonimizzati]'
        assert QuestionarioSonno.query.count() == 0


@pytest.mark.parametrize(
    ('route', 'mode', 'has_progress'),
    [
        ('/chi-sono', 'narrative', True),
        ('/faq', 'narrative', True),
        ('/iscrizione-corsi', 'narrative', True),
        ('/consulenze-online', 'narrative', True),
        ('/prestazioni-infermieristiche', 'narrative', True),
        ('/prenota', 'operational', False),
        ('/prenota-call-sonno', 'operational', False),
        ('/iscrizione-corsi/interesse', 'operational', False),
        ('/conferma', 'outcome', False),
        ('/iscrizione-accompagnamento/conferma', 'outcome', False),
        ('/iscrizione-corsi/interesse/conferma', 'outcome', False),
    ],
)
def test_pagine_interne_usano_regia_coerente_senza_snap(client, route, mode, has_progress):
    resp = client.get(route)

    assert resp.status_code == 200
    assert f'internal-page internal-page--{mode}' in resp.text
    assert f'data-internal-page="{mode}"' in resp.text
    assert 'css/internal-pages.css' in resp.text
    assert 'js/internal-page-motion.js' in resp.text
    assert ('data-internal-progress' in resp.text) is has_progress
    assert 'css/homepage.css' not in resp.text
    assert 'js/home-scroll-motion.js' not in resp.text


def test_regia_pagine_interne_non_entra_in_homepage_o_admin(client):
    homepage = client.get('/')
    login = client.get('/admin/login')

    for resp in (homepage, login):
        assert 'css/internal-pages.css' not in resp.text
        assert 'js/internal-page-motion.js' not in resp.text
        assert 'data-internal-page=' not in resp.text


@pytest.mark.parametrize('route', [
    '/privacy',
    '/condizioni-iscrizione-corsi',
    '/condizioni-consulenza-sonno',
])
def test_pagine_legali_caricano_subito_senza_dissolvenza_progressiva(client, route):
    response = client.get(route)

    assert response.status_code == 200
    assert 'css/internal-pages.css' in response.text
    assert 'js/internal-page-motion.js' not in response.text
    assert 'css/page-transitions.css' not in response.text
    assert 'js/page-transitions.js' not in response.text


def test_transizione_controllata_collega_le_pagine_ed_e_reversibile(client):
    homepage = client.get('/')
    root = Path(app_module.__file__).resolve().parent
    base_stylesheet = (root / 'static' / 'css' / 'base.css').read_text()
    transition_stylesheet = (root / 'static' / 'css' / 'page-transitions.css').read_text()
    transition_script = (root / 'static' / 'js' / 'page-transitions.js').read_text()

    assert homepage.status_code == 200
    assert 'css/page-transitions.css' in homepage.text
    assert 'js/page-transitions.js' in homepage.text
    assert '@view-transition' not in base_stylesheet
    assert '@media (min-width: 1024px) and (min-height: 640px)' in base_stylesheet
    assert '.site-header.is-scrolled .site-header__inner' in base_stylesheet
    assert 'height: 76px' in base_stylesheet
    assert 'prefers-reduced-motion: no-preference' in transition_stylesheet
    assert 'page-transition-enter-forward' in transition_stylesheet
    assert 'page-transition-enter-backward' in transition_stylesheet
    assert 'page-seam-forward' in transition_stylesheet
    assert 'transform: translateX(100vw)' in transition_stylesheet
    assert 'transform: translateX(-100vw)' in transition_stylesheet
    assert 'clip-path: inset(0 0 0 100%)' in transition_stylesheet
    assert 'clip-path: inset(0)' in transition_stylesheet
    assert 'page-transition-preview--forward' in transition_stylesheet
    assert 'page-transition-preview--backward' in transition_stylesheet
    assert 'page-transition-preview__frame' in transition_stylesheet
    assert 'page-home-progress-reveal' in transition_stylesheet
    assert "frame.setAttribute('sandbox', 'allow-same-origin')" in transition_script
    assert 'visibility: hidden !important' in transition_script
    assert 'height: 100svh !important' not in transition_script
    assert "parallaxStage?.classList.add('is-parallax-ready')" in transition_script
    assert "frame.addEventListener('load', checkReadiness" in transition_script
    assert 'scrollPreviewToDestination' in transition_script
    assert 'previewLoadTimeout = 1800' in transition_script
    assert 'navigateWithFallback' in transition_script
    assert "root.classList.add('page-transition-arrived')" in transition_script
    assert 'previewedNavigation\n        ? null' in transition_script
    assert "classList.contains('page-transition-arrived')" in (root / 'static' / 'js' / 'internal-page-motion.js').read_text()
    assert "returningHome ? 'backward' : 'forward'" in transition_script
    assert "event.persisted" in transition_script
    assert "destination.origin !== window.location.origin" in transition_script
    assert 'exitDuration' not in transition_script


def test_cta_sonno_homepage_apre_direttamente_le_tre_formule(client):
    homepage = client.get('/')

    assert homepage.status_code == 200
    assert 'href="/consulenze-online#formule"' in homepage.text
    assert 'data-conversion="home_pilastro_sonno"' in homepage.text


def test_bozza_dopo_la_nascita_non_e_pubblica(client):
    resp = client.get('/dopo-la-nascita')

    assert resp.status_code == 404


def test_homepage_usa_scene_singole_e_parallax_circoscritto(client):
    homepage = client.get('/')
    consultation = client.get('/consulenze-online')
    booking = client.get('/prenota')
    admin = client.get('/admin/login')

    assert 'data-home-parallax' in homepage.text
    assert 'selene-hero-home-background.jpg' in homepage.text
    assert 'selene-hero-home-subject.webp' in homepage.text
    assert 'home-hero-subject-clip' not in homepage.text
    assert 'data-home-parallax-foreground' in homepage.text
    assert homepage.text.count('data-home-scene=') == 7
    assert 'data-home-scene-nav' in homepage.text
    assert homepage.text.count('data-home-scene-chapter') == 3
    assert 'role="group" aria-label="Orientarsi"' in homepage.text
    assert 'role="group" aria-label="Conoscere"' in homepage.text
    assert 'role="group" aria-label="Scegliere"' in homepage.text
    assert 'data-home-scene-link="corsi"' in homepage.text
    assert 'data-home-scene-link="sonno"' in homepage.text
    assert homepage.text.count('home-scene-nav__link--pillar') == 2
    assert 'class="home-trust"' not in homepage.text
    assert 'Infermiera OPI Pescara' not in homepage.text
    assert 'Corsi pratici in presenza · Montesilvano' in homepage.text
    assert 'data-home-scene-link="date"' not in homepage.text
    assert 'class="home-course-families"' in homepage.text
    assert homepage.text.count('data-home-handoff-anchor=') == 4
    assert 'data-word-relay-anchor' not in homepage.text
    assert 'data-home-thread' not in homepage.text
    assert 'data-home-object-handoff' not in homepage.text
    assert 'data-home-scene-pulse' not in homepage.text
    assert 'js/scroll-echo.js' not in consultation.text
    assert 'js/home-scroll-motion.js' not in booking.text
    assert 'js/home-scroll-motion.js' not in admin.text


def test_css_rgba_letterali_solo_nei_token():
    css_directory = Path(app_module.__file__).resolve().parent / 'static' / 'css'
    tokens_path = css_directory / 'tokens.css'
    stylesheets = sorted(css_directory.glob('*.css'))

    for stylesheet in stylesheets:
        if stylesheet == tokens_path:
            continue
        assert 'rgba(' not in stylesheet.read_text().lower(), stylesheet.name

    tokens = tokens_path.read_text()
    alpha_definitions = re.findall(r'(--[a-z0-9-]+-a\d{2})\s*:\s*rgba\(', tokens)
    assert alpha_definitions
    assert len(alpha_definitions) == len(set(alpha_definitions))

    alpha_references = {
        token
        for stylesheet in stylesheets
        for token in re.findall(
            r'var\((--[a-z0-9-]+-a\d{2})\)',
            stylesheet.read_text(),
        )
    }
    assert alpha_references <= set(alpha_definitions)


def test_css_consulenza_caricato_nel_percorso_sonno(client):
    consultation = client.get('/consulenze-online')
    booking = client.get('/prenota-call-sonno')
    courses = client.get('/iscrizione-corsi')

    assert consultation.status_code == 200
    assert 'css/consulenza.css' in consultation.text
    assert 'css/homepage.css' not in consultation.text
    assert 'css/admin.css' not in consultation.text
    assert booking.status_code == 200
    assert 'css/consulenza.css' in booking.text
    assert courses.status_code == 200
    assert 'css/consulenza.css' not in courses.text
    assert 'css/homepage.css' not in courses.text
    assert 'css/admin.css' not in courses.text


def test_elenco_corsi_usa_foto_reale_per_laboratori(client):
    resp = client.get('/iscrizione-corsi')

    assert resp.status_code == 200
    assert 'img/laboratori-hero-esplorazione-sensoriale.jpg' in resp.text
    assert 'alt="Bambini impegnati in attività sensoriali durante un laboratorio"' in resp.text


def test_elenco_corsi_collega_immagini_titoli_e_cta(client):
    resp = client.get('/iscrizione-corsi')

    assert resp.status_code == 200
    directory_html = re.search(
        r'<div class="course-directory" id="elenco-corsi">(.*?)</div>\s*<div class="course-flow">',
        resp.text,
        re.DOTALL,
    ).group(1)
    course_paths = [
        '/iscrizione-corsi/blsd',
        '/iscrizione-corsi/disostruzione-pediatrica',
        '/iscrizione-corsi/accompagnamento-nascita',
        '/iscrizione-corsi/laboratorio-infanzia',
    ]
    for path in course_paths:
        assert directory_html.count(f'href="{path}"') == 3
    assert directory_html.count('class="course-directory-media"') == 4
    assert 'Scopri il corso' in directory_html
    assert "Scopri l'open day" in directory_html
    assert 'Scopri i laboratori' in directory_html
    assert '>Richiedi iscrizione<' not in directory_html


def test_elenco_corsi_mostra_edizioni_programmate_e_preseleziona_il_modulo(client):
    corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        titolo='Disostruzione settembre',
        data='2099-09-18',
        ora='18:30',
        luogo='S.C. Studio Infermieristico',
    )
    with flask_app.app_context():
        db.session.add(Corso(
            titolo='Laboratorio completo',
            tipo='laboratorio-infanzia',
            data='2099-09-20',
            ora='10:00',
            luogo='S.C. Studio Infermieristico',
            durata_ore=2,
            stato='Completo',
        ))
        db.session.add(Corso(
            titolo='Corso privato',
            tipo='bls-d',
            data='2099-09-21',
            ora='09:00',
            luogo='Azienda',
            durata_ore=5,
            stato='Chiuso',
        ))
        db.session.commit()

    resp = client.get('/iscrizione-corsi')

    assert resp.status_code == 200
    assert 'Corsi e laboratori in calendario' in resp.text
    assert 'Disostruzione settembre' in resp.text
    assert '18/09/2099' in resp.text
    assert 'Laboratorio completo' in resp.text
    assert 'Corso privato' not in resp.text
    assert f'/iscrizione-corsi/disostruzione-pediatrica?corso_id={corso_id}#modulo-iscrizione-corso' in resp.text

    modulo = client.get(f'/iscrizione-corsi/disostruzione-pediatrica?corso_id={corso_id}')
    assert re.search(rf'<option value="{corso_id}"[^>]* selected>', modulo.text)


def test_modulo_corso_separa_data_e_luogo_e_offre_ricontatto(client):
    corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        titolo='Disostruzione in studio',
        data='2099-09-18',
        ora='18:30',
        luogo='S.C. Studio Infermieristico',
    )

    resp = client.get('/iscrizione-corsi/disostruzione-pediatrica')

    assert resp.status_code == 200
    select_html = re.search(
        r'<select id="data_corso".*?</select>',
        resp.text,
        re.DOTALL,
    ).group(0)
    assert '18/09/2099 - ore 18:30' in select_html
    assert '>18/09/2099 - ore 18:30</option>' in select_html
    assert '>18/09/2099 - ore 18:30 - S.C. Studio Infermieristico</option>' not in select_html
    assert 'data-course-location="S.C. Studio Infermieristico"' in select_html
    assert 'id="luogo_corso"' in resp.text
    assert 'data-course-location-output value=""' in resp.text
    assert 'readonly' in resp.text
    assert 'Nessuna data è compatibile con le tue esigenze?' in resp.text
    assert (
        'href="/iscrizione-corsi/interesse?tematica=disostruzione-tagli-sicuri"'
        in resp.text
    )

    preselezionato = client.get(
        f'/iscrizione-corsi/disostruzione-pediatrica?corso_id={corso_id}'
    )
    assert re.search(rf'<option value="{corso_id}"[^>]* selected>', preselezionato.text)
    assert (
        'data-course-location-output value="S.C. Studio Infermieristico"'
        in preselezionato.text
    )


@pytest.mark.parametrize(
    ('corso_tipo', 'path', 'interest_topic'),
    [
        ('bls-d', '/iscrizione-corsi/blsd', 'blsd'),
        (
            'disostruzione-pediatrica',
            '/iscrizione-corsi/disostruzione-pediatrica',
            'disostruzione-tagli-sicuri',
        ),
        (
            'accompagnamento-nascita',
            '/iscrizione-corsi/accompagnamento-nascita',
            'accompagnamento-nascita',
        ),
        ('laboratorio-infanzia', '/iscrizione-corsi/laboratorio-infanzia', 'laboratori'),
    ],
)
def test_ogni_modulo_corso_espone_luogo_fisso_e_interesse_preselezionato(
    client,
    corso_tipo,
    path,
    interest_topic,
):
    _crea_data_corso(corso_tipo, luogo='S.C. Studio Infermieristico')

    resp = client.get(path)

    assert resp.status_code == 200
    assert 'data-course-date-select' in resp.text
    assert 'data-course-location-output' in resp.text
    assert 'aria-live="polite"' in resp.text
    assert f'href="/iscrizione-corsi/interesse?tematica={interest_topic}"' in resp.text


def test_modulo_interesse_preseleziona_solo_tematiche_valide(client):
    resp = client.get('/iscrizione-corsi/interesse?tematica=blsd')

    assert resp.status_code == 200
    assert '<option value="blsd" selected>BLSD</option>' in resp.text

    resp_non_valida = client.get('/iscrizione-corsi/interesse?tematica=non-prevista')
    assert 'value="non-prevista"' not in resp_non_valida.text
    assert '<option value="blsd" selected>' not in resp_non_valida.text


def test_testi_pubblici_mantengono_il_tu_senza_passare_al_voi(client):
    routes = ['/', '/chi-sono', '/consulenze-online', '/prenota-call-sonno']

    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200
        for plural_form in ('vostra', 'vostre', 'vostro', 'vostri'):
            assert re.search(rf'\b{plural_form}\b', resp.text, re.IGNORECASE) is None

    chi_sono = client.get('/chi-sono')
    assert 'Ti aiuto a leggere la situazione della tua famiglia' in chi_sono.text
    assert 'la sicurezza e la vita di ogni giorno' in chi_sono.text
    assert 'Da dove vuoi iniziare?' in chi_sono.text
    assert 'data-conversion="chi_sono_corsi"' in chi_sono.text
    assert 'data-conversion="chi_sono_sonno"' in chi_sono.text
    assert 'data-conversion="chi_sono_prestazioni"' in chi_sono.text
    assert chi_sono.text.index('chi_sono_corsi') < chi_sono.text.index('chi_sono_sonno')
    assert chi_sono.text.index('chi_sono_sonno') < chi_sono.text.index('chi_sono_prestazioni')


def test_css_admin_caricato_nel_login(client):
    resp = client.get('/admin/login')

    assert resp.status_code == 200
    assert 'css/tokens.css' in resp.text
    assert 'css/base.css' in resp.text
    assert 'css/components.css' in resp.text
    assert 'css/admin.css' in resp.text
    assert 'css/homepage.css' not in resp.text
    assert 'css/consulenza.css' not in resp.text
    assert 'css/stile.css' not in resp.text

    _login_admin(client)
    admin_resp = client.get('/admin')
    assert admin_resp.status_code == 200
    assert 'css/admin.css' in admin_resp.text
    assert 'css/homepage.css' not in admin_resp.text
    assert 'css/consulenza.css' not in admin_resp.text


def test_faq_include_flussi_aggiornati(client):
    resp = client.get('/faq')
    assert resp.status_code == 200
    assert 'consulenza del sonno' in resp.text
    assert 'BLSD' in resp.text
    assert 'link privato' in resp.text
    assert 'open day gratuito' in resp.text
    assert '0 a 12 mesi' not in resp.text
    assert '0-12' not in resp.text


def _prossimo_giorno_con_weekday(weekday):
    giorno = date.today()
    giorni_da_aggiungere = (weekday - giorno.weekday()) % 7
    if giorni_da_aggiungere == 0:
        giorni_da_aggiungere = 7
    return giorno + app_module.timedelta(days=giorni_da_aggiungere)


def _prossimo_sabato_non_festivo():
    giorno = _prossimo_giorno_con_weekday(5)
    while app_module.is_festivo(giorno):
        giorno += app_module.timedelta(days=7)
    return giorno


def _csrf_prenota(client):
    import re
    resp = client.get('/prenota')
    return re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)


def _csrf_iscrizione(client, corso_tipo):
    import re
    resp = client.get(f'/iscrizione-corsi/{corso_tipo}')
    return re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)


def _csrf_course_interest(client):
    resp = client.get('/iscrizione-corsi/interesse')
    return re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)


def test_pagina_disostruzione_presenta_contenuti_e_foto_del_corso(client):
    resp = client.get('/iscrizione-corsi/disostruzione-pediatrica')

    assert resp.status_code == 200
    assert 'Un corso teorico-pratico dedicato a genitori, nonni e caregiver' in resp.text
    assert 'Circa 2 ore e 30 minuti' in resp.text
    assert 'Manovre di disostruzione' in resp.text
    assert 'corso-disostruzione-copertina-studio.jpg' in resp.text
    assert 'corso-disostruzione-dimostrazione.jpg' in resp.text
    assert 'corso-disostruzione-prova-pratica.jpg' in resp.text
    assert 'corso-disostruzione-esercitazione-partecipanti.jpg' in resp.text
    assert 'corso-disostruzione-tagli-sicuri.jpg' in resp.text
    assert '<strong>Teoria</strong>' in resp.text
    assert '<strong>Prima prova pratica</strong>' in resp.text
    assert '<strong>Seconda prova pratica</strong>' in resp.text
    assert '<strong>Laboratorio tagli sicuri</strong>' in resp.text
    assert 'Selene nello studio' not in resp.text
    assert 'Per approfondire:' not in resp.text
    assert 'href="#richiesta-ricontatto"' in resp.text
    assert 'data-conversion="corso_disostruzione_modulo">Iscriviti ora</a>' in resp.text
    assert resp.text.count('<h1>') == 1


def test_pagina_laboratori_presenta_fasce_eta_e_foto_reali(client):
    resp = client.get('/iscrizione-corsi/laboratorio-infanzia')

    assert resp.status_code == 200
    assert resp.text.count('<h1>') == 1
    assert 'Laboratori per bambini e famiglie' in resp.text
    assert 'Attività da riproporre anche a casa' in resp.text
    assert '6-18' in resp.text
    assert '18-36' in resp.text
    assert '3-5' in resp.text
    assert 'laboratori-hero-esplorazione-sensoriale.jpg' in resp.text
    assert 'laboratori-primi-assaggi.jpg' in resp.text
    assert 'laboratori-autonomia-a-tavola.jpg' in resp.text
    assert 'laboratori-creativita-colori.jpg' in resp.text
    assert 'data-conversion="laboratorio_infanzia_modulo"' in resp.text


def test_pagina_accompagnamento_presenta_percorso_ed_equipe(client):
    resp = client.get('/corso-accompagnamento-nascita')

    assert resp.status_code == 200
    assert '8 incontri durante la gravidanza e 1 incontro dopo il parto' in resp.text
    assert 'Con l’ostetrica' in resp.text
    assert 'Con la psicologa' in resp.text
    assert 'Con l’osteopata' in resp.text
    assert 'Con la nutrizionista' in resp.text
    assert 'Con l’infermiera' in resp.text
    assert 'corso-accompagnamento-nascita-professionisti.jpg' in resp.text
    assert 'data-conversion="accompagnamento_open_day_hero"' in resp.text
    assert 'Scopri l’open day' in resp.text
    assert 'data-conversion="sticky_prima_della_nascita"' in resp.text
    assert 'In collaborazione con Farmacia Russo' in resp.text
    assert 'La Farmacia Russo collabora alla realizzazione del corso' in resp.text
    assert 'logo-farmacia-russo.png' in resp.text
    assert 'href="https://farmaciarussodomenico.it/"' in resp.text
    assert 'aria-label="Visita il sito della Farmacia Russo"' in resp.text
    assert 'Molto formativo grazie alle esperienze pratiche condivise dai professionisti' in resp.text
    assert resp.text.count('<h1>') == 1


def test_vecchio_url_prima_della_nascita_reindirizza_al_corso(client):
    resp = client.get('/prima-della-nascita')

    assert resp.status_code == 301
    assert resp.headers['Location'].endswith('/corso-accompagnamento-nascita')


def _crea_data_corso(
    corso_tipo,
    titolo='Corso test',
    data='2099-07-16',
    ora='18:00',
    luogo='Studio',
    capienza_massima=None,
):
    with flask_app.app_context():
        corso = Corso(
            titolo=titolo,
            tipo=corso_tipo,
            descrizione='Data aperta per test',
            data=data,
            ora=ora,
            luogo=luogo,
            durata_ore=2,
            capienza_massima=capienza_massima,
        )
        db.session.add(corso)
        db.session.commit()
        return str(corso.id)


def _crea_percorso_accompagnamento(slug='percorso-test', incontri=9, capienza_coppie=8):
    with flask_app.app_context():
        percorso = PercorsoAccompagnamento(
            titolo='Iscrizione al corso',
            slug=slug,
            descrizione='Edizione privata test',
            capienza_coppie=capienza_coppie,
            luogo='Studio',
            contatti='3806317175',
            stato='Aperto',
        )
        db.session.add(percorso)
        db.session.flush()
        professionisti = ['Infermiera', 'Ostetrica', 'Psicologa', 'Osteopata', 'Nutrizionista']
        for numero in range(1, incontri + 1):
            db.session.add(IncontroAccompagnamento(
                percorso=percorso,
                numero=numero,
                data=f'2099-08-{numero:02d}',
                ora='17:00',
                professionista=professionisti[(numero - 1) % len(professionisti)],
                tema=f'Incontro {numero}',
                luogo='Studio',
            ))
        db.session.commit()
        return percorso.slug, percorso.id


def test_iscrizione_disostruzione_salva_richiesta(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'nome_bambino': 'Luca',
        'eta_bambino': '3 anni',
        'partecipazione': 'Singolo 34 euro',
        'nome_secondo_partecipante': 'Dato da ignorare',
        'codice_fiscale_secondo_partecipante': 'IGNORA80A01G482X',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/conferma'
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.corso_tipo == 'disostruzione-pediatrica'
        assert iscrizione.nome == 'Mario Rossi'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'richiesta_iscrizione'
        assert iscrizione.posti == 1
        assert iscrizione.persona is None
        assert iscrizione.extra_dict()['nome_bambino'] == 'Luca'
        assert iscrizione.extra_dict()['eta_bambino'] == '3 anni'
        assert iscrizione.extra_dict()['nome_secondo_partecipante'] == ''
        assert iscrizione.extra_dict()['codice_fiscale_secondo_partecipante'] == ''
        assert iscrizione.extra_dict()['condizioni_corso_versione'] == '2026-08-30'
        assert iscrizione.extra_dict()['condizioni_corso_accettate_il']
        assert '16/07/2099' in iscrizione.data_corso
        assert iscrizione.stato == 'Nuova'
        assert PersonaCorso.query.count() == 0


def test_iscrizione_corso_senza_condizioni_viene_rifiutata_lato_server(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
    )
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    response = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert response.status_code == 200
    assert 'Devi dichiarare di aver letto e accettato le Condizioni di iscrizione ai corsi.' in response.text
    assert 'data-course-form-error data-error-field="condizioni_corso"' in response.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0


def test_invio_modulo_corso_notifica_solo_lo_studio_e_chiarisce_che_il_posto_non_e_confermato(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
    )
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
            'nome': 'Mario Rossi',
            'codice_fiscale': 'RSSMRA80A01G482X',
            'telefono': '3331234567',
            'email': 'mario@example.com',
            'partecipazione': 'Singolo 34 euro',
            'data_corso': data_corso_id,
            'scopo_informativo': 'on',
            'no_certificazione': 'on',
            'buono_stato_salute': 'on',
            'consenso_privacy': 'on',
            'condizioni_corso': 'on',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    assert send_mock.call_count == 1
    alert = send_mock.call_args.args[0]
    assert alert.recipients == [flask_app.config['MAIL_ADMIN_RECIPIENT']]
    assert 'mario@example.com' not in alert.recipients

    conferma = client.get('/iscrizione-corsi/conferma')
    assert '<h1>Richiesta ricevuta</h1>' in conferma.text
    assert 'Il posto non è ancora confermato.' in conferma.text
    assert 'non riceverai una mail automatica' in conferma.text
    assert 'soltanto quando l’iscrizione sarà confermata' in conferma.text


def test_iscrizione_con_data_richiede_email_per_la_conferma_successiva(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
    )
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 200
    assert 'verrà usato per comunicarti la conferma del posto' in resp.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0


def test_admin_conferma_e_annulla_iscrizione_inviando_una_sola_mail_per_transizione(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        luogo='S.C. Studio Infermieristico',
    )
    with flask_app.app_context():
        iscrizione = IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099 - ore 18:00 - S.C. Studio Infermieristico · lista d’attesa',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add(iscrizione)
        db.session.commit()
        iscrizione_id = iscrizione.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send') as send_mock:
        conferma = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Confermato',
            data={'_csrf_token': csrf},
        )
        duplicata = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Confermato',
            data={'_csrf_token': csrf},
        )
        annullamento = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Annullato',
            data={'_csrf_token': csrf},
        )

    assert conferma.status_code == duplicata.status_code == annullamento.status_code == 302
    assert send_mock.call_count == 2
    conferma_msg, annullamento_msg = [call.args[0] for call in send_mock.call_args_list]
    assert conferma_msg.recipients == ['mario@example.com']
    assert conferma_msg.subject == 'Posto confermato - Disostruzione pediatrica'
    assert 'il tuo posto per Disostruzione pediatrica è confermato' in conferma_msg.body
    assert 'Data e luogo: 16/07/2099 - ore 18:00 - S.C. Studio Infermieristico' in conferma_msg.body
    assert 'lista d’attesa' not in conferma_msg.body
    assert annullamento_msg.recipients == ['mario@example.com']
    assert annullamento_msg.subject == 'Iscrizione annullata - Disostruzione pediatrica'
    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.stato == 'Annullato'
        patient = PersonaCorso.query.one()
        assert iscrizione.persona_id == patient.id
        assert patient.nome == 'Mario Rossi'
        assert patient.telefono == '3331234567'
        assert patient.email == 'mario@example.com'
        assert patient.codice_fiscale == 'RSSMRA80A01G482X'
        audit = app_module.RegistroModifica.query.filter_by(
            azione='creazione_anagrafica_da_conferma',
            entita_tipo='PersonaCorso',
            entita_id=patient.id,
        ).one()
        assert json.loads(audit.dettagli)['pratica_id'] == iscrizione_id


def test_conferma_iscrizione_riusa_il_paziente_solo_con_codice_fiscale(client):
    data_corso_id = _crea_data_corso(
        'laboratorio-infanzia',
        "Laboratorio per l'infanzia",
        data='2099-09-20',
    )
    with flask_app.app_context():
        patient = PersonaCorso(
            nome='Anna Neri',
            telefono='3330000000',
            email='vecchia@example.com',
            codice_fiscale='NRENNA90A41G482Z',
        )
        registration = IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='laboratorio-infanzia',
            corso_titolo="Laboratorio per l'infanzia",
            nome='Anna Neri aggiornata',
            telefono='3331234567',
            email='anna@example.com',
            codice_fiscale='NRENNA90A41G482Z',
            data_corso='20/09/2099 - ore 18:00 - S.C. Studio Infermieristico',
            partecipazione='Iscrizione individuale',
            dati_extra=json.dumps({
                'nome_bambino': 'Leo',
                'eta_bambino': '18 mesi',
            }),
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add_all([patient, registration])
        db.session.commit()
        patient_id = patient.id
        registration_id = registration.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send'):
        response = client.post(
            f'/admin/iscrizione-corso/{registration_id}/Confermato',
            data={'_csrf_token': csrf},
        )

    assert response.status_code == 302
    with flask_app.app_context():
        assert PersonaCorso.query.count() == 1
        registration = db.session.get(IscrizioneCorso, registration_id)
        patient = db.session.get(PersonaCorso, patient_id)
        assert registration.persona_id == patient_id
        assert patient.nome == 'Anna Neri aggiornata'
        assert patient.telefono == '3331234567'
        assert patient.email == 'anna@example.com'
        assert patient.nome_bambino == 'Leo'
        assert patient.eta_bambino == '18 mesi'
        link_audit = app_module.RegistroModifica.query.filter_by(
            azione='collegamento_paziente_automatico',
            entita_tipo='IscrizioneCorso',
            entita_id=registration_id,
        ).one()
        assert json.loads(link_audit.dettagli)['nuova_anagrafica'] is False


def test_errore_mail_conferma_non_annulla_lo_stato_salvato(client):
    data_corso_id = _crea_data_corso(
        'bls-d',
        'Corso BLSD',
        data='2099-09-18',
        luogo='S.C. Studio Infermieristico',
    )
    with flask_app.app_context():
        iscrizione = IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='bls-d',
            corso_titolo='Corso BLSD',
            nome='Giulia Bianchi',
            telefono='3331234567',
            email='giulia@example.com',
            codice_fiscale='BNCGLI85A41G482Z',
            data_corso='18/09/2099 - ore 18:00 - S.C. Studio Infermieristico',
            partecipazione='Iscrizione individuale',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add(iscrizione)
        db.session.commit()
        iscrizione_id = iscrizione.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Confermato',
            data={'_csrf_token': csrf},
        )

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.persona is not None
        assert iscrizione.persona.nome == 'Giulia Bianchi'
        assert PersonaCorso.query.count() == 1
        email = EmailOperativa.query.filter_by(
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione_id,
        ).one()
        assert email.stato == 'fallita'
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione_id,
        ).one()
        assert 'conferma iscrizione corso' in evento.messaggio


def test_spostamento_iscrizione_invia_la_nuova_edizione_senza_confermare_il_posto(client):
    origine_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione settembre',
        data='2099-09-18',
        luogo='S.C. Studio Infermieristico',
    )
    destinazione_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione ottobre',
        data='2099-10-03',
        ora='10:00',
        luogo='Sala partner',
    )
    with flask_app.app_context():
        iscrizione = IscrizioneCorso(
            corso_id=int(origine_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione settembre',
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='18/09/2099 - ore 18:00 - S.C. Studio Infermieristico',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add(iscrizione)
        db.session.commit()
        iscrizione_id = iscrizione.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/sposta',
            data={
                '_csrf_token': csrf,
                'corso_destinazione_id': destinazione_id,
            },
        )

    assert resp.status_code == 302
    assert send_mock.call_count == 1
    messaggio = send_mock.call_args.args[0]
    assert messaggio.recipients == ['mario@example.com']
    assert 'Edizione precedente: 18/09/2099' in messaggio.body
    assert 'Nuova edizione: 03/10/2099 - ore 10:00 - Sala partner' in messaggio.body
    assert 'Il posto non è ancora confermato' in messaggio.body
    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.corso_id == int(destinazione_id)
        assert iscrizione.stato == 'Nuova'


def test_errore_email_non_perde_iscrizione_corso(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
    )
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
            'nome': 'Mario Rossi',
            'codice_fiscale': 'RSSMRA80A01G482X',
            'telefono': '3331234567',
            'email': 'mario@example.com',
            'partecipazione': 'Singolo 34 euro',
            'data_corso': data_corso_id,
            'scopo_informativo': 'on',
            'no_certificazione': 'on',
            'buono_stato_salute': 'on',
            'consenso_privacy': 'on',
            'condizioni_corso': 'on',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione.id,
        ).one()
        assert evento.esito == 'errore'
        assert 'non inviata' in evento.messaggio


def test_iscrizione_laboratorio_infanzia_salva_richiesta(client):
    data_corso_id = _crea_data_corso(
        'laboratorio-infanzia',
        "Laboratorio per l'infanzia",
        data='2099-07-21',
        ora='17:00',
    )
    token = _csrf_iscrizione(client, 'laboratorio-infanzia')

    resp = client.post('/iscrizione-corsi/laboratorio-infanzia', data={
        'nome': 'Anna Neri',
        'codice_fiscale': 'NRENNA90A41G482Z',
        'telefono': '3331234567',
        'email': 'anna@example.com',
        'nome_bambino': 'Leo',
        'eta_bambino': '18 mesi',
        'partecipazione': 'Iscrizione individuale',
        'data_corso': data_corso_id,
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/conferma'
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.corso_tipo == 'laboratorio-infanzia'
        assert iscrizione.corso_titolo == 'Laboratori svezzamento, gioco e sviluppo'
        assert iscrizione.tipo_richiesta == 'richiesta_iscrizione'
        assert iscrizione.posti == 1
        assert iscrizione.persona is None
        assert iscrizione.extra_dict()['nome_bambino'] == 'Leo'
        assert iscrizione.extra_dict()['eta_bambino'] == '18 mesi'
        assert PersonaCorso.query.count() == 0


def test_iscrizione_blsd_salva_richiesta_individuale(client):
    data_corso_id = _crea_data_corso('bls-d', 'Corso BLSD', data='2099-07-17', ora='09:00')
    token = _csrf_iscrizione(client, 'blsd')

    resp = client.post('/iscrizione-corsi/blsd', data={
        'nome': 'Giulia Bianchi',
        'codice_fiscale': 'BNCGLI85A41G482Z',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'partecipazione': 'Iscrizione individuale',
        'data_corso': data_corso_id,
        'prove_pratiche': 'on',
        'buono_stato_salute': 'on',
        'richiesta_non_conferma': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/conferma'
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        extra = iscrizione.extra_dict()
        assert iscrizione.corso_tipo == 'bls-d'
        assert iscrizione.corso_titolo == 'Corso BLSD'
        assert iscrizione.partecipazione == 'Iscrizione individuale'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'richiesta_iscrizione'
        assert iscrizione.posti == 1
        assert '17/07/2099' in iscrizione.data_corso
        assert not iscrizione.consenso_immagini
        assert 'ente_azienda' not in extra
        assert 'numero_partecipanti' not in extra


def test_pagina_blsd_usa_nuovo_slug_e_reindirizza_quello_precedente(client):
    resp = client.get('/iscrizione-corsi/blsd')

    assert resp.status_code == 200
    assert 'action="/iscrizione-corsi/blsd"' in resp.text
    assert '<link rel="canonical" href="http://localhost/iscrizione-corsi/blsd">' in resp.text
    assert 'img/corso-blsd-esercitazione.jpg' in resp.text
    assert '5 ore' in resp.text
    assert 'Teoria ed esercitazioni pratiche su manichino' in resp.text
    assert 'Cittadini, associazioni, aziende e gruppi' in resp.text
    assert 'Via C. D’Agnese 43, 65015 Montesilvano (PE)' in resp.text

    redirect_resp = client.get('/iscrizione-corsi/bls-d')

    assert redirect_resp.status_code == 301
    assert redirect_resp.headers['Location'] == '/iscrizione-corsi/blsd'


def test_iscrizione_blsd_non_accetta_azienda_da_form(client):
    data_corso_id = _crea_data_corso('bls-d', 'Corso BLSD', data='2099-07-17', ora='09:00')
    token = _csrf_iscrizione(client, 'blsd')

    resp = client.post('/iscrizione-corsi/blsd', data={
        'nome': 'Giulia Bianchi',
        'codice_fiscale': 'BNCGLI85A41G482Z',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'partecipazione': 'Azienda o gruppo',
        'data_corso': data_corso_id,
        'prove_pratiche': 'on',
        'buono_stato_salute': 'on',
        'richiesta_non_conferma': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 200
    assert 'Seleziona il tipo di partecipazione.' in resp.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0


def test_iscrizione_accompagnamento_compare_in_admin(client):
    data_corso_id = _crea_data_corso(
        'accompagnamento-nascita',
        'Corso di accompagnamento alla nascita',
        data='2099-07-18',
        ora='10:00',
    )
    token = _csrf_iscrizione(client, 'accompagnamento-nascita')

    resp = client.post('/iscrizione-corsi/accompagnamento-nascita', data={
        'nome': 'Luisa Verdi',
        'codice_fiscale': 'VRDLSU90A41G482Y',
        'telefono': '3331234567',
        'email': 'luisa@example.com',
        'data_nascita': '1990-01-01',
        'luogo_nascita': 'Pescara',
        'indirizzo': 'Via Roma 1',
        'citta': 'Montesilvano',
        'provincia': 'PE',
        'cap': '65015',
        'data_presunta_parto': '2026-12-01',
        'settimana_gravidanza': '20',
        'gravidanza_regolare': 'Si',
        'data_corso': data_corso_id,
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        'consenso_dati_gravidanza': 'on',
        'conferma_finale': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    csrf = _login_admin(client)
    admin_resp = client.get('/admin')
    assert 'Luisa Verdi' in admin_resp.text
    assert 'Corso di accompagnamento alla nascita' in admin_resp.text
    stato_resp = client.post('/admin/iscrizione-corso/1/Contattato', data={'_csrf_token': csrf})
    assert stato_resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.first()
        assert iscrizione.stato == 'Contattato'
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.tipo_richiesta == 'open_day'


def test_iscrizione_senza_date_salva_richiesta_ricontatto(client):
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.data_corso == 'Da ricontattare per prossime date'
        assert iscrizione.corso_id is None
        assert iscrizione.tipo_richiesta == 'ricontatto'
        assert iscrizione.posti == 0
        assert iscrizione.extra_dict()['richiesta_prossime_date'] is True


def test_ricontatto_blsd_non_richiede_checkbox_ridondanti(client):
    page = client.get('/iscrizione-corsi/blsd')
    token = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)

    assert 'id="richiesta-ricontatto"' in page.text
    assert 'name="prove_pratiche"' not in page.text
    assert 'name="conferma_finale"' not in page.text
    assert page.text.count('name="buono_stato_salute"') == 1

    response = client.post('/iscrizione-corsi/blsd', data={
        'nome': 'Giulia Bianchi',
        'codice_fiscale': 'BNCGLI85A41G482Z',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'partecipazione': 'Iscrizione individuale',
        'buono_stato_salute': 'on',
        'richiesta_non_conferma': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert response.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.tipo_richiesta == 'ricontatto'
        assert iscrizione.extra_dict()['buono_stato_salute'] is True
        assert 'prove_pratiche' not in iscrizione.extra_dict()


def test_modulo_interesse_corsi_raccoglie_temi_senza_dati_da_iscrizione(client):
    resp = client.get('/iscrizione-corsi/interesse')

    assert resp.status_code == 200
    assert '<h1>Quale corso ti interessa?</h1>' in resp.text
    assert 'Disostruzione pediatrica e tagli sicuri' in resp.text
    assert '>BLSD<' in resp.text
    assert '>Accompagnamento alla nascita<' in resp.text
    assert "Laboratori per l&#39;infanzia" in resp.text
    assert '>Gioco e sviluppo<' in resp.text
    assert 'name="codice_fiscale"' not in resp.text
    assert 'name="consenso_privacy"' in resp.text
    assert 'data-conversion="course_interest_submit"' in resp.text


def test_modulo_interesse_corsi_salva_ricontatto_senza_occupare_posti(client):
    token = _csrf_course_interest(client)

    resp = client.post('/iscrizione-corsi/interesse', data={
        'nome': 'Giulia Bianchi',
        'telefono': '3331234567',
        'email': 'giulia@example.com',
        'tematica': 'gioco-sviluppo',
        'note': 'Preferenza per il sabato mattina.',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-corsi/interesse/conferma'
    with flask_app.app_context():
        interesse = IscrizioneCorso.query.one()
        assert interesse.corso_id is None
        assert interesse.corso_tipo == 'laboratorio-infanzia'
        assert interesse.corso_titolo == 'Gioco e sviluppo'
        assert interesse.codice_fiscale == ''
        assert interesse.tipo_richiesta == 'ricontatto'
        assert interesse.posti == 0
        assert interesse.consenso_privacy is True
        assert interesse.note == 'Preferenza per il sabato mattina.'
        assert interesse.extra_dict()['tematica_interesse'] == 'gioco-sviluppo'
        assert interesse.persona is None
        assert PersonaCorso.query.count() == 0


def test_modulo_interesse_corsi_rifiuta_tematica_non_prevista(client):
    token = _csrf_course_interest(client)

    resp = client.post('/iscrizione-corsi/interesse', data={
        'nome': 'Giulia Bianchi',
        'telefono': '3331234567',
        'tematica': 'corso-non-previsto',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 200
    assert 'Seleziona il corso o la tematica che ti interessa.' in resp.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0


def test_conferma_interesse_corsi_chiarisce_che_non_e_iscrizione(client):
    resp = client.get('/iscrizione-corsi/interesse/conferma')

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert 'Potrai valutarla prima di decidere se richiedere l’iscrizione.' in resp.text
    assert '<meta name="robots" content="noindex,nofollow">' in resp.text
    assert 'data-conversion="course_interest_confirmation_home"' in resp.text


def test_accompagnamento_senza_date_collega_callout_a_modulo_ricontatto(client):
    resp = client.get('/iscrizione-corsi/accompagnamento-nascita')
    assert resp.status_code == 200
    assert 'Vuoi ricevere un avviso quando apre il prossimo open day?' in resp.text
    assert 'href="#richiesta-ricontatto"' in resp.text
    assert 'id="richiesta-ricontatto"' in resp.text
    assert 'Modulo di ricontatto' in resp.text


def test_iscrizione_coppia_occupa_due_posti(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Coppia 60 euro',
        'data_corso': data_corso_id,
        'nome_secondo_partecipante': 'Luisa Verdi',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.posti == 2
        assert iscrizione.extra_dict()['nome_secondo_partecipante'] == 'Luisa Verdi'
        assert iscrizione.extra_dict()['codice_fiscale_secondo_partecipante'] == ''


def test_modulo_disostruzione_mostra_secondo_partecipante_solo_per_coppia(client):
    _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')

    response = client.get('/iscrizione-corsi/disostruzione-pediatrica')

    assert response.status_code == 200
    assert 'data-second-participant-fields hidden' in response.text
    assert 'Nome secondo partecipante *' in response.text
    assert re.search(r'name="nome_secondo_partecipante"[^>]* disabled', response.text)
    assert 'Codice fiscale secondo partecipante</label>' in response.text
    assert 'Codice fiscale secondo partecipante *</label>' not in response.text


def test_errore_iscrizione_corso_indica_e_riporta_al_campo_telefono(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    response = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '123',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert response.status_code == 200
    assert 'data-course-registration-form' in response.text
    assert 'data-course-form-error data-error-field="telefono"' in response.text
    assert 'Inserisci un numero di telefono valido.' in response.text
    assert 'value="123"' in response.text


def test_data_piena_resta_selezionabile_come_lista_attesa(client):
    data_piena_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Prima data',
        data='2099-07-16',
        capienza_massima=1,
    )
    data_successiva_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Data successiva',
        data='2099-07-23',
        capienza_massima=8,
    )
    with flask_app.app_context():
        db.session.add(IscrizioneCorso(
            corso_id=int(data_piena_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Prima data',
            nome='Persona già iscritta',
            telefono='3331234567',
            email='iscritta@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
            stato='Nuova',
        ))
        db.session.commit()

    resp = client.get('/iscrizione-corsi/disostruzione-pediatrica')

    assert resp.status_code == 200
    assert f'value="{data_piena_id}"' in resp.text
    assert 'lista d’attesa' in resp.text
    assert f'value="{data_successiva_id}"' in resp.text
    with flask_app.app_context():
        panoramica = app_module._panoramica_corsi(
            [db.session.get(Corso, int(data_piena_id))]
        )
        assert panoramica[0]['stato'] == 'Completo'
        assert panoramica[0]['posti_liberi'] == 0


def test_coppia_ammessa_con_un_posto_residuo(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        capienza_massima=2,
    )
    with flask_app.app_context():
        db.session.add(IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Persona già iscritta',
            telefono='3331234567',
            email='iscritta@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
            stato='Nuova',
        ))
        db.session.commit()
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Luisa Verdi',
        'codice_fiscale': 'VRDLSU90A41G482Y',
        'telefono': '3337654321',
        'email': 'luisa@example.com',
        'partecipazione': 'Coppia 60 euro',
        'data_corso': data_corso_id,
        'nome_secondo_partecipante': 'Mario Verdi',
        'codice_fiscale_secondo_partecipante': 'VRDMRA80A01G482Z',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 2
        coppia = IscrizioneCorso.query.filter_by(nome='Luisa Verdi').one()
        assert coppia.posti == 2
        corso = db.session.get(Corso, int(data_corso_id))
        assert app_module._posti_liberi_corso(corso) == 0
        assert not app_module._corso_ha_posti(corso)


def test_annullamento_riapre_automaticamente_la_data(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        capienza_massima=1,
    )
    with flask_app.app_context():
        db.session.add(IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Persona annullata',
            telefono='3331234567',
            email='annullata@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
            stato='Annullato',
        ))
        db.session.commit()

    resp = client.get('/iscrizione-corsi/disostruzione-pediatrica')

    assert resp.status_code == 200
    assert f'value="{data_corso_id}"' in resp.text


def test_data_piena_senza_successiva_crea_lista_attesa(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        capienza_massima=1,
    )
    with flask_app.app_context():
        db.session.add(IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Persona già iscritta',
            telefono='3331234567',
            email='iscritta@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
            stato='Nuova',
        ))
        db.session.commit()
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    resp = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Luisa Verdi',
        'codice_fiscale': 'VRDLSU90A41G482Y',
        'telefono': '3337654321',
        'email': 'luisa@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.filter_by(nome='Luisa Verdi').one()
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.stato == 'Lista attesa'
        assert iscrizione.posti == 0
        assert iscrizione.posti_richiesti == 1
        assert iscrizione.persona is not None
        assert iscrizione.persona.nome == 'Luisa Verdi'
        assert iscrizione.persona.telefono == '3337654321'
        assert iscrizione.persona.email == 'luisa@example.com'
        assert iscrizione.persona.codice_fiscale == 'VRDLSU90A41G482Y'
        assert PersonaCorso.query.count() == 1
        consent = ConsensoPrivacyPaziente.query.one()
        assert consent.persona_id == iscrizione.persona_id
        assert consent.entita_tipo == 'IscrizioneCorso'
        assert consent.entita_id == iscrizione.id
        assert consent.accettato is True
        assert consent.accettato_il == iscrizione.creato_il
        audit = app_module.RegistroModifica.query.filter_by(
            azione='creazione_anagrafica_da_lista_attesa',
            entita_tipo='PersonaCorso',
            entita_id=iscrizione.persona_id,
        ).one()
        assert json.loads(audit.dettagli)['pratica_id'] == iscrizione.id


def test_lista_attesa_riusa_paziente_con_codice_fiscale_esatto(client):
    data_corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        capienza_massima=1,
    )
    with flask_app.app_context():
        existing_patient = PersonaCorso(
            nome='Luisa Verdi precedente',
            telefono='3330000000',
            email='precedente@example.com',
            codice_fiscale='VRDLSU90A41G482Y',
        )
        registration = IscrizioneCorso(
            corso_id=int(data_corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Persona già iscritta',
            telefono='3331234567',
            email='iscritta@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add_all([existing_patient, registration])
        db.session.commit()
        existing_patient_id = existing_patient.id
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    response = client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Luisa Verdi',
        'codice_fiscale': 'vrdlsu90a41g482y',
        'telefono': '3337654321',
        'email': 'luisa@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    assert response.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.filter_by(nome='Luisa Verdi').one()
        patient = db.session.get(PersonaCorso, existing_patient_id)
        assert iscrizione.stato == 'Lista attesa'
        assert iscrizione.persona_id == existing_patient_id
        assert PersonaCorso.query.count() == 1
        assert patient.nome == 'Luisa Verdi'
        assert patient.telefono == '3337654321'
        assert patient.email == 'luisa@example.com'
        assert app_module.RegistroModifica.query.filter_by(
            azione='creazione_anagrafica_da_lista_attesa',
        ).count() == 0


def test_passaggio_admin_a_lista_attesa_crea_e_collega_il_paziente(client):
    with flask_app.app_context():
        registration = IscrizioneCorso(
            corso_tipo='blsd',
            corso_titolo='BLSD',
            nome='Paolo Blu',
            telefono='3339876543',
            email='paolo@example.com',
            codice_fiscale='BLUPLA80A01G482X',
            data_corso='Da definire',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Nuova',
        )
        db.session.add(registration)
        db.session.commit()
        registration_id = registration.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/iscrizione-corso/{registration_id}/Lista attesa',
        data={'_csrf_token': csrf},
    )

    assert response.status_code == 302
    with flask_app.app_context():
        registration = db.session.get(IscrizioneCorso, registration_id)
        assert registration.stato == 'Lista attesa'
        assert registration.posti == 1
        assert registration.persona is not None
        assert registration.persona.nome == 'Paolo Blu'
        assert PersonaCorso.query.count() == 1


def test_stato_lista_attesa_ripetuto_collega_una_pratica_storica(client):
    with flask_app.app_context():
        registration = IscrizioneCorso(
            corso_tipo='blsd',
            corso_titolo='BLSD',
            nome='Marta Viola',
            telefono='3331112233',
            email='marta@example.com',
            codice_fiscale='VLIMRT80A41G482X',
            data_corso='Da definire',
            tipo_richiesta='richiesta_iscrizione',
            posti=0,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Lista attesa',
        )
        db.session.add(registration)
        db.session.commit()
        registration_id = registration.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/iscrizione-corso/{registration_id}/Lista attesa',
        data={'_csrf_token': csrf},
    )

    assert response.status_code == 302
    with flask_app.app_context():
        registration = db.session.get(IscrizioneCorso, registration_id)
        assert registration.stato == 'Lista attesa'
        assert registration.persona is not None
        assert registration.persona.nome == 'Marta Viola'
        assert PersonaCorso.query.count() == 1


def test_admin_mostra_panoramica_iscritti_per_corso(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    token = _csrf_iscrizione(client, 'disostruzione-pediatrica')

    client.post('/iscrizione-corsi/disostruzione-pediatrica', data={
        'nome': 'Mario Rossi',
        'codice_fiscale': 'RSSMRA80A01G482X',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'partecipazione': 'Singolo 34 euro',
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        'condizioni_corso': 'on',
        '_csrf_token': token,
    })

    _login_admin(client)
    resp = client.get(f'/admin?corso_id={data_corso_id}')
    assert resp.status_code == 200
    assert 'Corsi attivi e richieste da gestire' in resp.text
    assert 'Disostruzione pediatrica' in resp.text
    assert 'posti stimati' in resp.text
    assert 'Richiesta iscrizione' in resp.text
    assert f'href="/admin/pratica/Corso/{data_corso_id}#partecipanti-corso"' in resp.text

    scheda = client.get(f'/admin/pratica/Corso/{data_corso_id}')
    assert scheda.status_code == 200
    assert 'id="partecipanti-corso"' in scheda.text
    assert 'Partecipanti iscritti' in scheda.text
    assert 'Mario Rossi' in scheda.text
    assert scheda.text.index('Partecipanti iscritti') < scheda.text.index('Modifica corso')


def test_admin_filtra_iscritti_per_tipologia_corso(client):
    with flask_app.app_context():
        disostruzione = IscrizioneCorso(
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='2099-07-16',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
        )
        blsd = IscrizioneCorso(
            corso_tipo='bls-d',
            corso_titolo='BLSD',
            nome='Giulia Bianchi',
            telefono='3337654321',
            email='giulia@example.com',
            codice_fiscale='BNCGLI85A41G482Z',
            data_corso='2099-07-17',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            consenso_privacy=True,
        )
        db.session.add_all([disostruzione, blsd])
        db.session.commit()

    _login_admin(client)
    resp = client.get('/admin?tipo_corso=disostruzione-pediatrica')
    assert resp.status_code == 200
    assert 'Visualizza richieste per tipologia' in resp.text
    assert 'Disostruzione pediatrica' in resp.text
    assert 'Mario Rossi' in resp.text
    assert 'Giulia Bianchi' not in resp.text


def test_admin_aggiunge_iscritto_manualmente_e_crea_rubrica(client):
    data_corso_id = _crea_data_corso(
        'laboratorio-infanzia',
        "Laboratorio per l'infanzia",
        data='2099-07-20',
        ora='17:00',
    )
    csrf = _login_admin(client)

    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post('/admin/iscrizione-corso/aggiungi', data={
            'corso_id': data_corso_id,
            'nome': 'Anna Neri',
            'telefono': '3331234567',
            'email': 'anna@example.com',
            'codice_fiscale': '',
            'nome_bambino': 'Leo',
            'eta_bambino': '18 mesi',
            'tipo_richiesta': 'iscrizione_effettiva',
            'stato': 'Confermato',
            'posti': '1',
            'partecipazione': 'Bambino/a',
            'note': 'Prenotata da Instagram',
            'note_persona': 'Preferisce laboratorio pomeridiano',
            'consenso_privacy': 'on',
            '_csrf_token': csrf,
        })

    assert resp.status_code == 302
    assert resp.headers['Location'] == f'/admin?corso_id={data_corso_id}#admin-corsi'
    assert send_mock.call_count == 1
    assert send_mock.call_args.args[0].recipients == ['anna@example.com']
    with flask_app.app_context():
        persona = PersonaCorso.query.one()
        iscrizione = IscrizioneCorso.query.one()
        assert persona.nome == 'Anna Neri'
        assert persona.nome_bambino == 'Leo'
        assert persona.eta_bambino == '18 mesi'
        assert 'pomeridiano' in persona.note
        assert iscrizione.persona_id == persona.id
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.tipo_richiesta == 'iscrizione_effettiva'
        assert iscrizione.posti == 1
        assert iscrizione.codice_fiscale == ''
        assert iscrizione.extra_dict()['inserimento_admin'] is True


def test_admin_rifiuta_open_day_manuale_per_corsi_diversi_da_accompagnamento(client):
    corso_id = _crea_data_corso('bls-d', 'BLSD', data='2099-07-21')
    csrf = _login_admin(client)

    response = client.post('/admin/iscrizione-corso/aggiungi', data={
        'corso_id': corso_id,
        'tipo_richiesta': 'open_day',
        'nome': 'Anna Neri',
        'telefono': '3331234567',
        '_csrf_token': csrf,
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'Il flusso open day è disponibile soltanto per il corso di accompagnamento alla nascita.' in response.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0
        assert PersonaCorso.query.count() == 0


def test_admin_richiama_persona_da_rubrica_senza_duplicarla(client):
    data_corso_id = _crea_data_corso('disostruzione-pediatrica', 'Disostruzione pediatrica')
    with flask_app.app_context():
        persona = PersonaCorso(
            nome='Anna Neri',
            telefono='3331234567',
            email='anna@example.com',
            nome_bambino='Leo',
            eta_bambino='18 mesi',
        )
        db.session.add(persona)
        db.session.commit()
        persona_id = persona.id

    csrf = _login_admin(client)
    resp = client.post('/admin/iscrizione-corso/aggiungi', data={
        'corso_id': data_corso_id,
        'persona_id': str(persona_id),
        'tipo_richiesta': 'richiesta_iscrizione',
        'stato': 'Nuova',
        'posti': '1',
        'partecipazione': 'Iscrizione individuale',
        'consenso_privacy': 'on',
        '_csrf_token': csrf,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        assert PersonaCorso.query.count() == 1
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.persona_id == persona_id
        assert iscrizione.nome == 'Anna Neri'
        assert iscrizione.telefono == '3331234567'
        assert iscrizione.extra_dict()['nome_bambino'] == 'Leo'


def test_chiusure_studio_disabilitano_domeniche_festivi_e_sabato_pomeriggio(client):
    """Domeniche e festivi devono bloccare tutti gli orari; il sabato solo dopo le 11:30."""
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    resp_domenica = client.get(f'/api/orari-occupati/{domenica}')
    assert set(resp_domenica.get_json()) == set(app_module.ORARI_DISPONIBILI)

    resp_festivo = client.get('/api/orari-occupati/2099-12-25')
    assert set(resp_festivo.get_json()) == set(app_module.ORARI_DISPONIBILI)

    sabato = _prossimo_sabato_non_festivo().strftime('%Y-%m-%d')
    resp_sabato = client.get(f'/api/orari-occupati/{sabato}')
    orari_sabato = set(resp_sabato.get_json())
    assert '11:30' not in orari_sabato
    assert '12:00' in orari_sabato
    assert '12:30' in orari_sabato
    assert '15:00' in orari_sabato


def test_prenotazione_rifiutata_se_studio_chiuso(client):
    """Il server deve rifiutare una prenotazione inviata in un giorno di chiusura."""
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    token = _csrf_prenota(client)

    resp = client.post('/prenota', data={
        'nome': 'Mario Rossi', 'telefono': '333 1234567', 'email': 'mario@example.com',
        'servizio': 'Medicazione semplice', 'data': domenica, 'ora': '10:00',
        'consenso_privacy': 'on', '_csrf_token': token
    })

    assert 'studio è chiuso' in resp.text
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


def test_errore_email_non_perde_prenotazione_e_viene_registrato(client):
    giorno = _prossimo_giorno_con_weekday(1).strftime('%Y-%m-%d')
    token = _csrf_prenota(client)

    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post('/prenota', data={
            'nome': 'Mario Rossi',
            'telefono': '333 1234567',
            'email': 'mario@example.com',
            'servizio': 'Medicazione semplice',
            'data': giorno,
            'ora': '10:00',
            'consenso_privacy': 'on',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/conferma'
    with flask_app.app_context():
        appuntamento = Appuntamento.query.one()
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            esito='errore',
            entita_tipo='Appuntamento',
            entita_id=appuntamento.id,
        ).one()
        assert appuntamento.stato == 'In attesa'
        assert appuntamento.consenso_privacy is True
        assert 'non inviata' in evento.messaggio


def test_login_admin_ignora_redirect_esterno(client):
    """Il parametro next non deve poter portare l'admin verso domini esterni."""
    from werkzeug.security import generate_password_hash

    with flask_app.app_context():
        if not Admin.query.filter_by(username='admin').first():
            db.session.add(Admin(username='admin', password=generate_password_hash('cambiami123')))
            db.session.commit()

    token = _csrf_prenota(client)
    resp = client.post('/admin/login?next=https://example.com', data={
        'username': 'admin',
        'password': 'cambiami123',
        '_csrf_token': token
    })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/admin'


def test_admin_mostra_i_timestamp_persistiti_nel_fuso_italiano(client):
    _login_admin(client)
    with flask_app.app_context():
        db.session.add(RegistroEvento(
            categoria='audit',
            esito='info',
            messaggio='Correzione registrata.',
            creato_il=datetime(2026, 8, 26, 18, 46),
        ))
        db.session.commit()

    response = client.get('/admin')

    assert response.status_code == 200
    assert '26/08/2026' in response.text
    assert '20:46 CEST' in response.text
    assert '18:46' not in response.text


def test_dettaglio_appuntamento_esplicita_stato_pratica_e_calendar(client):
    _login_admin(client)
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Medicazione semplice',
            data='2099-09-18',
            ora='10:00',
            stato='Confermato',
            sincronizzazione='mancante',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id

    response = client.get(f'/admin/pratica/Appuntamento/{appuntamento_id}')

    assert response.status_code == 200
    assert '<small>Stato appuntamento</small><span class="badge">Confermato</span>' in response.text
    assert '<small>Google Calendar</small><span class="sync-chip sync-mancante">mancante</span>' in response.text


def test_admin_mostra_nome_accanto_all_id_nei_log_e_negli_errori(client):
    _login_admin(client)
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Ada Persona',
            telefono='3331234567',
            email='ada@example.com',
            servizio='Medicazione semplice',
            data='2099-09-18',
            ora='10:00',
        )
        db.session.add(appuntamento)
        db.session.flush()
        evento = RegistroEvento(
            categoria='google_calendar',
            esito='errore',
            messaggio='Sincronizzazione non riuscita.',
            entita_tipo='Appuntamento',
            entita_id=appuntamento.id,
        )
        db.session.add(evento)
        db.session.commit()
        riferimento = f'Appuntamento #{appuntamento.id} · Ada Persona'

    response = client.get('/admin#admin-errori')

    assert response.status_code == 200
    assert riferimento in response.text
    assert '<strong class="admin-primary">Appuntamento</strong>' in response.text
    assert '<span>Ada Persona</span>' in response.text


def test_admin_separa_nuovo_corso_e_propone_il_luogo_dello_studio(client):
    _login_admin(client)

    response = client.get('/admin#admin-nuovo-corso')

    assert response.status_code == 200
    assert 'data-admin-target="nuovo-corso"' in response.text
    nuovo_corso = re.search(
        r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="nuovo-corso" id="admin-nuovo-corso">(.*?)</section>',
        response.text,
        re.DOTALL,
    ).group(1)
    assert '<h2>Crea nuovo corso</h2>' in nuovo_corso
    assert 'action="/admin/corso/aggiungi"' in nuovo_corso
    assert 'id="course-place-admin" value="S.C. Studio Infermieristico"' in nuovo_corso
    assert '<table' not in nuovo_corso


def test_admin_separa_corsi_attivi_da_passati_e_annullati(client):
    oggi = app_module.local_today().isoformat()
    with flask_app.app_context():
        db.session.add_all([
            Corso(titolo='Corso di oggi', tipo='bls-d', data=oggi, stato='Aperto'),
            Corso(titolo='Edizione futura attiva', tipo='bls-d', data='2099-12-01', stato='Completo'),
            Corso(titolo='Corso passato', tipo='bls-d', data='2000-01-01', stato='Concluso'),
            Corso(titolo='Edizione annullata', tipo='bls-d', data='2099-12-02', stato='Annullato'),
        ])
        db.session.commit()

    _login_admin(client)
    response = client.get('/admin#admin-corsi')

    assert response.status_code == 200
    assert 'data-admin-target="archivio-corsi"' in response.text
    corsi_attivi = re.search(
        r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="corsi">(.*?)</section>',
        response.text,
        re.DOTALL,
    ).group(1)
    archivio_corsi = re.search(
        r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="archivio-corsi" id="admin-archivio-corsi">(.*?)</section>',
        response.text,
        re.DOTALL,
    ).group(1)

    assert 'Corso di oggi' in corsi_attivi
    assert 'Edizione futura attiva' in corsi_attivi
    assert 'Corso passato' not in corsi_attivi
    assert 'Edizione annullata' not in corsi_attivi
    assert 'Corso passato' in archivio_corsi
    assert 'Edizione annullata' in archivio_corsi
    assert 'Corso di oggi' not in archivio_corsi
    assert 'Edizione futura attiva' not in archivio_corsi


def test_admin_mostra_solo_richieste_da_gestire_e_conserva_confermate_nell_archivio(client):
    with flask_app.app_context():
        corso_archiviato = Corso(
            titolo='Edizione storica disostruzione',
            tipo='disostruzione-pediatrica',
            data='2000-05-20',
            stato='Concluso',
            capienza_massima=12,
        )
        corso_attivo = Corso(
            titolo='Edizione futura disostruzione',
            tipo='disostruzione-pediatrica',
            data='2099-05-20',
            stato='Aperto',
            capienza_massima=12,
        )
        db.session.add_all([corso_archiviato, corso_attivo])
        db.session.flush()

        def iscrizione(nome, stato, corso=None, tipo_richiesta='richiesta_iscrizione', posti=1):
            return IscrizioneCorso(
                corso_id=corso.id if corso else None,
                corso_tipo=corso.tipo if corso else 'disostruzione-pediatrica',
                corso_titolo=corso.titolo if corso else 'Prossime date disostruzione',
                nome=nome,
                telefono='3331234567',
                email=f'{nome.lower().replace(" ", ".")}@example.com',
                codice_fiscale='',
                data_corso=corso.data if corso else 'Da ricontattare per prossime date',
                tipo_richiesta=tipo_richiesta,
                posti=posti,
                posti_richiesti=posti,
                consenso_privacy=True,
                stato=stato,
            )

        db.session.add_all([
            iscrizione('Confermata storica', 'Confermato', corso_archiviato, posti=2),
            iscrizione('Nuova storica', 'Nuova', corso_archiviato),
            iscrizione('Confermata futura', 'Confermato', corso_attivo),
            iscrizione('Persona in attesa', 'Lista attesa', corso_attivo, posti=0),
            iscrizione('Persona da ricontattare', 'Confermato', tipo_richiesta='ricontatto', posti=0),
            iscrizione('Richiesta annullata', 'Annullato', corso_attivo),
        ])
        db.session.commit()
        corso_archiviato_id = corso_archiviato.id

    _login_admin(client)
    response = client.get('/admin#admin-corsi')

    assert response.status_code == 200
    corsi_panel = re.search(
        r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="corsi" id="admin-corsi">(.*?)</section>',
        response.text,
        re.DOTALL,
    ).group(1)
    assert '3 richieste da gestire' in corsi_panel
    assert 'Nuova storica' in corsi_panel
    assert 'Persona in attesa' in corsi_panel
    assert 'Persona da ricontattare' in corsi_panel
    assert 'Confermata storica' not in corsi_panel
    assert 'Confermata futura' not in corsi_panel
    assert 'Richiesta annullata' not in corsi_panel

    archivio_corsi = re.search(
        r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="archivio-corsi" id="admin-archivio-corsi">(.*?)</section>',
        response.text,
        re.DOTALL,
    ).group(1)
    assert 'Edizione storica disostruzione' in archivio_corsi
    assert '<strong>1</strong> richiesta confermata' in archivio_corsi
    assert '2 posti confermati' in archivio_corsi

    dettaglio = client.get(f'/admin/pratica/Corso/{corso_archiviato_id}')
    assert dettaglio.status_code == 200
    assert 'Confermata storica' in dettaglio.text


def test_admin_mostra_filtro_open_day_solo_per_accompagnamento_nascita(client):
    with flask_app.app_context():
        def richiesta(nome, corso_tipo, tipo_richiesta):
            return IscrizioneCorso(
                corso_tipo=corso_tipo,
                corso_titolo='Richiesta corso',
                nome=nome,
                telefono='3331234567',
                email='',
                codice_fiscale='',
                tipo_richiesta=tipo_richiesta,
                posti=1,
                posti_richiesti=1,
                consenso_privacy=True,
                stato='Nuova',
            )

        db.session.add_all([
            richiesta('Open day nascita', 'accompagnamento-nascita', 'open_day'),
            richiesta('Richiesta nascita standard', 'accompagnamento-nascita', 'richiesta_iscrizione'),
            richiesta('Dato storico open day BLSD', 'bls-d', 'open_day'),
        ])
        db.session.commit()

    _login_admin(client)
    default_response = client.get('/admin#admin-corsi')
    blsd_response = client.get('/admin?tipo_corso=bls-d#admin-corsi')
    nascita_response = client.get('/admin?tipo_corso=accompagnamento-nascita#admin-corsi')
    open_day_response = client.get(
        '/admin?tipo_corso=accompagnamento-nascita&iscrizioni=open_day#admin-corsi'
    )
    open_day_blsd_response = client.get('/admin?tipo_corso=bls-d&iscrizioni=open_day#admin-corsi')

    def pannello_corsi(response):
        return re.search(
            r'<section class="pagina-interna admin-page admin-panel" data-admin-panel="corsi" id="admin-corsi">(.*?)</section>',
            response.text,
            re.DOTALL,
        ).group(1)

    link_open_day = (
        'href="/admin?tipo_corso=accompagnamento-nascita&amp;iscrizioni=open_day#admin-corsi"'
    )
    assert link_open_day not in pannello_corsi(default_response)
    assert link_open_day not in pannello_corsi(blsd_response)
    assert link_open_day in pannello_corsi(nascita_response)
    assert 'Open day nascita' in pannello_corsi(open_day_response)
    assert 'Richiesta nascita standard' not in pannello_corsi(open_day_response)
    assert 'Dato storico open day BLSD' in pannello_corsi(open_day_blsd_response)
    assert 'Stai vedendo solo le iscrizioni agli open day.' not in pannello_corsi(open_day_blsd_response)


# ─── Integrazione Google Calendar (Arzamed) ───

@pytest.fixture
def calendario_finto(app, monkeypatch):
    """Inietta risposte Calendar API senza contattare Google."""
    eventi_per_data = {
        '2026-08-03': [{
            'id': 'chiusura-ricorrente-20260803',
            'start': {'dateTime': '2026-08-03T15:00:00+02:00'},
            'end': {'dateTime': '2026-08-03T16:00:00+02:00'},
            'recurringEventId': 'chiusura-ricorrente',
        }],
        '2099-08-11': [{
            'id': 'appuntamento-arzamed-1',
            'start': {'dateTime': '2099-08-11T10:00:00+02:00'},
            'end': {'dateTime': '2099-08-11T11:00:00+02:00'},
        }],
        '2026-08-17': [{
            'id': 'chiusura-ricorrente-20260817',
            'start': {'dateTime': '2026-08-17T15:00:00+02:00'},
            'end': {'dateTime': '2026-08-17T16:00:00+02:00'},
            'recurringEventId': 'chiusura-ricorrente',
        }],
    }
    mock_servizio = MagicMock()

    def risposta_lista(**parametri):
        risposta = MagicMock()
        data_richiesta = parametri['timeMin'][:10]
        risposta.execute.return_value = {
            'items': eventi_per_data.get(data_richiesta, []),
        }
        return risposta

    mock_servizio.events.return_value.list.side_effect = risposta_lista
    app_module.app.config['GOOGLE_CALENDAR_ID'] = 'finto@group.calendar.google.com'
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = '/percorso/finto/service-account.json'
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: mock_servizio)
    app_module._invalida_cache_calendario()
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._azzera_stato_calendario()


def test_errore_lettura_calendar_usa_cache_e_viene_registrato(app, monkeypatch):
    intervalli = [(
        datetime.fromisoformat('2099-08-11T10:00:00+02:00'),
        datetime.fromisoformat('2099-08-11T11:00:00+02:00'),
        'evento-cache',
    )]
    chiave_cache = ('calendar@example.invalid', '2099-08-11')
    app_module._cache_calendario['per_data'][chiave_cache] = {
        'intervalli': intervalli,
        'scaricato_il': time.monotonic() - 301,
    }
    app_module._cache_calendario['errore_registrato_il'] = 0
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(app.config, 'CALENDARIO_CACHE_SECONDI', 300)
    mock_servizio = MagicMock()
    mock_servizio.events.return_value.list.return_value.execute.side_effect = RuntimeError('rete assente')
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: mock_servizio)

    with app.app_context():
        risultato = app_module._scarica_intervalli_calendario('2099-08-11')
        eventi = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
        ).all()

    assert risultato == intervalli
    assert len(eventi) == 1
    assert 'Lettura del calendario non disponibile' in eventi[0].messaggio
    app_module._azzera_stato_calendario()


def test_staging_senza_opt_in_non_contatta_calendar(app, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'staging')
    monkeypatch.setitem(app.config, 'STAGING_LIVE_INTEGRATIONS', False)
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(
        app.config,
        'GOOGLE_SERVICE_ACCOUNT_FILE',
        '/etc/secrets/google-calendar-service-account.json',
    )
    app_module._azzera_stato_calendario()

    with patch.object(
        app_module.service_account.Credentials,
        'from_service_account_file',
    ) as crea_credenziali, patch.object(
        app_module,
        'build',
    ) as crea_servizio, app.app_context():
        risultato = app_module._scarica_intervalli_calendario('2099-08-11')
        servizio = app_module._ottieni_servizio_calendario()
        eventi = RegistroEvento.query.filter_by(categoria='google_calendar').all()

    assert risultato == []
    assert servizio is None
    assert eventi == []
    crea_credenziali.assert_not_called()
    crea_servizio.assert_not_called()
    app_module._azzera_stato_calendario()


def test_calendario_google_blocca_appuntamento_singolo(calendario_finto):
    """Un appuntamento Arzamed (10:00-11:00) deve bloccare gli slot 10:00 e 10:30."""
    occupati = app_module.orari_occupati_da_calendario('2099-08-11')
    assert occupati == {'10:00', '10:30'}


def test_calendario_google_riceve_ricorrenze_espanse_dalla_api(calendario_finto):
    """La API deve espandere la chiusura ricorrente nelle singole occorrenze."""
    occupati_originale = app_module.orari_occupati_da_calendario('2026-08-03')
    occupati_successivo = app_module.orari_occupati_da_calendario('2026-08-17')
    assert occupati_originale == {'15:00', '15:30'}
    assert occupati_successivo == {'15:00', '15:30'}
    for chiamata in calendario_finto.events.return_value.list.call_args_list:
        assert chiamata.kwargs['singleEvents'] is True


def test_calendario_google_nessun_evento(calendario_finto):
    """Un giorno senza eventi non deve risultare bloccato."""
    assert app_module.orari_occupati_da_calendario('2026-08-12') == set()


def test_calendar_api_gestisce_paginazione_e_eventi_giornalieri(app, monkeypatch):
    prima_pagina = MagicMock()
    prima_pagina.execute.return_value = {
        'items': [{
            'id': 'evento-mattina',
            'start': {'dateTime': '2026-08-18T09:00:00+02:00'},
            'end': {'dateTime': '2026-08-18T10:00:00+02:00'},
        }],
        'nextPageToken': 'pagina-2',
    }
    seconda_pagina = MagicMock()
    seconda_pagina.execute.return_value = {
        'items': [{
            'id': 'chiusura-giornaliera',
            'start': {'date': '2026-08-18'},
            'end': {'date': '2026-08-19'},
        }],
    }
    mock_servizio = MagicMock()
    mock_servizio.events.return_value.list.side_effect = [
        prima_pagina,
        seconda_pagina,
    ]
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: mock_servizio)
    app_module._invalida_cache_calendario()

    intervalli = app_module._scarica_intervalli_calendario('2026-08-18')

    assert len(intervalli) == 2
    assert mock_servizio.events.return_value.list.call_count == 2
    seconda_chiamata = mock_servizio.events.return_value.list.call_args_list[1]
    assert seconda_chiamata.kwargs['pageToken'] == 'pagina-2'
    assert seconda_chiamata.kwargs['singleEvents'] is True
    app_module._azzera_stato_calendario()


def test_google_calendar_usa_scope_limitato_agli_eventi(app, monkeypatch):
    credenziali = object()
    client = MagicMock()
    trasporto = object()
    http_autorizzato = object()
    monkeypatch.setitem(
        app.config,
        'GOOGLE_SERVICE_ACCOUNT_FILE',
        '/percorso/finto/google-calendar-service-account.json',
    )
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_TIMEOUT_SECONDI', 5)
    app_module._azzera_stato_calendario()

    with patch.object(
        app_module.service_account.Credentials,
        'from_service_account_file',
        return_value=credenziali,
    ) as crea_credenziali, patch.object(
        app_module.httplib2,
        'Http',
        return_value=trasporto,
    ) as crea_trasporto, patch.object(
        app_module.google_auth_httplib2,
        'AuthorizedHttp',
        return_value=http_autorizzato,
    ) as autorizza_trasporto, patch.object(
        app_module,
        'build',
        return_value=client,
    ) as crea_servizio:
        risultato = app_module._ottieni_servizio_calendario()

    assert risultato is client
    assert crea_credenziali.call_args.kwargs['scopes'] == [
        'https://www.googleapis.com/auth/calendar.events',
    ]
    crea_trasporto.assert_called_once_with(timeout=5)
    autorizza_trasporto.assert_called_once_with(credenziali, http=trasporto)
    assert crea_servizio.call_args.kwargs['http'] is http_autorizzato
    assert 'credentials' not in crea_servizio.call_args.kwargs
    app_module._azzera_stato_calendario()


def test_google_calendar_crea_un_trasporto_distinto_per_operazione(app, monkeypatch):
    credenziali = object()
    trasporti = [object(), object()]
    http_autorizzati = [object(), object()]
    servizi = [object(), object()]
    monkeypatch.setitem(
        app.config,
        'GOOGLE_SERVICE_ACCOUNT_FILE',
        '/percorso/finto/google-calendar-service-account.json',
    )
    app_module._azzera_stato_calendario()

    with patch.object(
        app_module.service_account.Credentials,
        'from_service_account_file',
        return_value=credenziali,
    ), patch.object(
        app_module.httplib2,
        'Http',
        side_effect=trasporti,
    ), patch.object(
        app_module.google_auth_httplib2,
        'AuthorizedHttp',
        side_effect=http_autorizzati,
    ) as autorizza_trasporto, patch.object(
        app_module,
        'build',
        side_effect=servizi,
    ) as crea_servizio:
        primo = app_module._ottieni_servizio_calendario()
        secondo = app_module._ottieni_servizio_calendario()

    assert [primo, secondo] == servizi
    assert autorizza_trasporto.call_args_list[0].kwargs['http'] is trasporti[0]
    assert autorizza_trasporto.call_args_list[1].kwargs['http'] is trasporti[1]
    assert crea_servizio.call_args_list[0].kwargs['http'] is http_autorizzati[0]
    assert crea_servizio.call_args_list[1].kwargs['http'] is http_autorizzati[1]


def test_letture_calendar_concorrenti_eseguono_un_solo_fetch(app, monkeypatch):
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(app.config, 'CALENDARIO_CACHE_SECONDI', 300)
    app_module._azzera_stato_calendario()
    servizio = MagicMock()
    barriera = threading.Barrier(8)

    def risposta_lenta(**_parametri):
        richiesta = MagicMock()

        def esegui(**_opzioni):
            time.sleep(0.05)
            return {'items': []}

        richiesta.execute.side_effect = esegui
        return richiesta

    servizio.events.return_value.list.side_effect = risposta_lenta
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: servizio)

    def leggi_giorno():
        barriera.wait()
        return app_module._scarica_intervalli_calendario('2099-08-11')

    with ThreadPoolExecutor(max_workers=8) as esecutore:
        risultati = list(esecutore.map(lambda _indice: leggi_giorno(), range(8)))

    assert risultati == [[]] * 8
    assert servizio.events.return_value.list.call_count == 1


@pytest.mark.parametrize('tipo_errore', ['http_404', 'timeout', 'ssl'])
def test_errori_calendar_aprono_il_circuito_senza_abbattere_il_sito(
    app,
    client,
    monkeypatch,
    tipo_errore,
):
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(app.config, 'CALENDARIO_CACHE_ERRORE_SECONDI', 30)
    app_module._azzera_stato_calendario()
    if tipo_errore == 'http_404':
        risposta = MagicMock(status=404, reason='Not Found')
        errore = HttpError(risposta, b'{"error": "not found"}')
    elif tipo_errore == 'timeout':
        errore = TimeoutError('Calendar non risponde')
    else:
        errore = ssl.SSLError('Handshake TLS fallito')

    servizio = MagicMock()
    servizio.events.return_value.list.return_value.execute.side_effect = errore
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: servizio)

    with app.app_context():
        prima = app_module._scarica_intervalli_calendario('2099-08-11')
        seconda = app_module._scarica_intervalli_calendario('2099-08-12')
        eventi = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
        ).all()

    assert prima == []
    assert seconda == []
    assert servizio.events.return_value.list.call_count == 1
    assert len(eventi) == 1
    assert client.get('/healthz').status_code == 200


def test_endpoint_orari_occupati_unisce_db_e_calendario(client, calendario_finto):
    """L'endpoint /api/orari-occupati deve unire prenotazioni dal sito e impegni Arzamed."""
    with flask_app.app_context():
        appt = Appuntamento(
            nome='Prenotazione dal sito', telefono='333', email='sito@example.com',
            servizio='Test', data='2099-08-11', ora='16:00', stato='Confermato'
        )
        db.session.add(appt)
        db.session.commit()

    resp = client.get('/api/orari-occupati/2099-08-11')
    orari = set(resp.get_json())
    # 10:00/10:30 vengono da Arzamed (calendario), 16:00 dalla prenotazione sul sito
    assert orari == {'10:00', '10:30', '16:00'}


def test_prenotazione_rifiutata_se_occupata_su_calendario(client, calendario_finto):
    """Il server deve rifiutare una prenotazione per un orario già occupato su Arzamed,
    anche bypassando il controllo JavaScript lato client."""
    resp = client.get('/prenota')
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)

    resp = client.post('/prenota', data={
        'nome': 'Mario Rossi', 'telefono': '333 1234567', 'email': 'mario@example.com',
        'servizio': 'Medicazione semplice', 'data': '2099-08-11', 'ora': '10:00',
        'consenso_privacy': 'on', '_csrf_token': token
    })
    assert 'non è più disponibile' in resp.text
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


# ─── Scrittura su Google Calendar (conferma/spostamento/annullamento) ───

def _login_admin(client):
    """Helper: garantisce che esista un admin, effettua il login e restituisce
    un token CSRF valido per le azioni successive nell'area admin.

    Nota: il token CSRF usato per il login viene "consumato" (rimosso dalla
    sessione) dal server durante il controllo del login stesso, quindi non è
    riutilizzabile per le richieste successive: ne va letto uno nuovo dopo
    il login, ricaricando una pagina che lo rigeneri (es. /admin).
    """
    import re
    from werkzeug.security import generate_password_hash

    with flask_app.app_context():
        if not Admin.query.filter_by(username='admin').first():
            db.session.add(Admin(username='admin', password=generate_password_hash('cambiami123')))
            db.session.commit()

    resp = client.get('/admin/login')
    token_login = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)
    client.post('/admin/login', data={'username': 'admin', 'password': 'cambiami123', '_csrf_token': token_login})

    resp = client.get('/admin')
    with client.session_transaction() as sess:
        token_azioni = sess.get('_csrf_token')
    assert token_azioni, 'Login admin fallito: impossibile ottenere un token CSRF valido.'
    return token_azioni


def _csrf_admin(client):
    client.get('/admin')
    with client.session_transaction() as sess:
        token = sess.get('_csrf_token')
    assert token
    return token


def test_modulo_privato_accompagnamento_rifiuta_condizioni_mancanti(client):
    slug, _ = _crea_percorso_accompagnamento(slug='percorso-condizioni-test')
    response = client.get(f'/iscrizione-accompagnamento/{slug}')
    token = re.search(r'name="_csrf_token" value="([^"]+)"', response.text).group(1)

    response = client.post(f'/iscrizione-accompagnamento/{slug}', data={
        'nome': 'Luisa Verdi',
        'telefono': '3331234567',
        'email': 'luisa@example.com',
        'codice_fiscale': 'VRDLSU90A41G482Y',
        'data_presunta_parto': '2100-01-10',
        'partner_presente': 'Si',
        'consenso_privacy': 'on',
        'consenso_dati_gravidanza': 'on',
        '_csrf_token': token,
    })

    assert response.status_code == 200
    assert 'Devi dichiarare di aver letto e accettato le Condizioni di iscrizione ai corsi.' in response.text
    with flask_app.app_context():
        assert IscrizioneCorso.query.count() == 0
        assert PresenzaAccompagnamento.query.count() == 0


def test_modulo_privato_accompagnamento_conferma_iscrizione_e_presenze(client):
    slug, percorso_id = _crea_percorso_accompagnamento()
    resp = client.get(f'/iscrizione-accompagnamento/{slug}')
    assert resp.status_code == 200
    assert 'infermiera, ostetrica, psicologa, osteopata e nutrizionista' in resp.text
    assert 'name="condizioni_corso" required' in resp.text
    assert 'href="/condizioni-iscrizione-corsi"' in resp.text
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)

    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(f'/iscrizione-accompagnamento/{slug}', data={
            'nome': 'Luisa Verdi',
            'telefono': '3331234567',
            'email': 'luisa@example.com',
            'codice_fiscale': 'VRDLSU90A41G482Y',
            'data_presunta_parto': '2100-01-10',
            'partner_presente': 'Si',
            'consenso_privacy': 'on',
            'condizioni_corso': 'on',
            'consenso_dati_gravidanza': 'on',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-accompagnamento/conferma'
    assert send_mock.call_count == 1
    assert send_mock.call_args.args[0].recipients == [flask_app.config['MAIL_ADMIN_RECIPIENT']]
    pagina_conferma = client.get('/iscrizione-accompagnamento/conferma')
    assert '<h1>Richiesta ricevuta</h1>' in pagina_conferma.text
    assert 'Il posto non è ancora confermato.' in pagina_conferma.text
    assert 'non riceverai una mail automatica' in pagina_conferma.text
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        iscrizione_id = iscrizione.id
        extra = iscrizione.extra_dict()
        assert extra['condizioni_corso_versione'] == '2026-08-30'
        assert extra['condizioni_corso_accettate_il']
        assert iscrizione.percorso_accompagnamento_id == percorso_id
        assert iscrizione.stato == 'Nuova'
        assert iscrizione.tipo_richiesta == 'iscrizione_effettiva'
        assert iscrizione.posti == 1
        assert iscrizione.partecipazione == 'Coppia - partner si'
        assert extra['data_presunta_parto'] == '2100-01-10'
        assert extra['partner_presente'] == 'Si'
        assert iscrizione.consenso_immagini is False
        assert iscrizione.consenso_dati_gravidanza is True
        assert iscrizione.consenso_dati_gravidanza_il is not None
        assert iscrizione.persona is None
        assert PersonaCorso.query.count() == 0
        assert PresenzaAccompagnamento.query.count() == 9

    csrf = _login_admin(client)
    dettaglio = client.get(f'/admin/pratica/IscrizioneCorso/{iscrizione_id}')
    assert 'Condizioni corsi' in dettaglio.text
    assert 'Accettate · versione 2026-08-30' in dettaglio.text
    with patch.object(app_module.mail, 'send') as confirmation_send:
        stato_resp = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Confermato',
            data={'_csrf_token': csrf},
        )

    assert stato_resp.status_code == 302
    assert confirmation_send.call_count == 1
    messaggio = confirmation_send.call_args.args[0]
    assert messaggio.recipients == ['luisa@example.com']
    assert 'Iscrizione confermata' in messaggio.subject
    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.persona is not None
        assert iscrizione.persona.nome == 'Luisa Verdi'
        assert iscrizione.persona.codice_fiscale == 'VRDLSU90A41G482Y'
        assert PersonaCorso.query.count() == 1


def test_capienza_percorso_privato_blocca_e_annullamento_riapre(client):
    slug, percorso_id = _crea_percorso_accompagnamento(
        slug='percorso-capienza-test',
        capienza_coppie=1,
    )
    with flask_app.app_context():
        percorso = db.session.get(PercorsoAccompagnamento, percorso_id)
        iscrizione = IscrizioneCorso(
            percorso_accompagnamento=percorso,
            corso_tipo='accompagnamento-nascita',
            corso_titolo=percorso.titolo,
            nome='Luisa Verdi',
            telefono='3331234567',
            email='luisa@example.com',
            codice_fiscale='VRDLSU90A41G482Y',
            data_corso='Percorso di 9 incontri',
            partecipazione='Coppia - partner si',
            tipo_richiesta='iscrizione_effettiva',
            posti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        db.session.add(iscrizione)
        db.session.commit()
        iscrizione_id = iscrizione.id

    pieno = client.get(f'/iscrizione-accompagnamento/{slug}')
    assert pieno.status_code == 200
    assert 'Iscrizioni non disponibili' in pieno.text
    assert 'name="codice_fiscale"' not in pieno.text

    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        iscrizione.stato = 'Annullato'
        db.session.commit()

    riaperto = client.get(f'/iscrizione-accompagnamento/{slug}')
    assert riaperto.status_code == 200
    assert 'name="codice_fiscale"' in riaperto.text


def test_errori_email_non_perdono_iscrizione_e_presenze_del_percorso(client):
    slug, _ = _crea_percorso_accompagnamento(
        slug='percorso-email-test',
        capienza_coppie=2,
    )
    resp = client.get(f'/iscrizione-accompagnamento/{slug}')
    token = re.search(r'name="_csrf_token" value="([^"]+)"', resp.text).group(1)

    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post(f'/iscrizione-accompagnamento/{slug}', data={
            'nome': 'Luisa Verdi',
            'telefono': '3331234567',
            'email': 'luisa@example.com',
            'codice_fiscale': 'VRDLSU90A41G482Y',
            'data_presunta_parto': '2100-01-10',
            'partner_presente': 'Si',
            'consenso_privacy': 'on',
            'condizioni_corso': 'on',
            'consenso_dati_gravidanza': 'on',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        iscrizione_id = iscrizione.id
        assert iscrizione.stato == 'Nuova'
        assert PresenzaAccompagnamento.query.count() == 9
        eventi = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione.id,
        ).all()
        assert len(eventi) == 1
        assert all(evento.esito == 'errore' for evento in eventi)

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP ancora non disponibile')):
        conferma = client.post(
            f'/admin/iscrizione-corso/{iscrizione_id}/Confermato',
            data={'_csrf_token': csrf},
        )

    assert conferma.status_code == 302
    with flask_app.app_context():
        iscrizione = db.session.get(IscrizioneCorso, iscrizione_id)
        assert iscrizione.stato == 'Confermato'
        eventi = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione.id,
        ).all()
        assert len(eventi) == 2
        assert any('conferma percorso' in evento.messaggio for evento in eventi)


def test_percorso_accompagnamento_chiuso_offre_un_contatto_utilizzabile(client):
    slug, percorso_id = _crea_percorso_accompagnamento(slug='percorso-chiuso-test')
    with flask_app.app_context():
        percorso = db.session.get(PercorsoAccompagnamento, percorso_id)
        percorso.stato = 'Chiuso'
        db.session.commit()

    resp = client.get(f'/iscrizione-accompagnamento/{slug}')

    assert resp.status_code == 200
    assert 'Iscrizioni non disponibili' in resp.text
    assert 'href="tel:3806317175"' in resp.text
    assert 'data-conversion="birth_private_closed_phone"' in resp.text


def test_conferma_accompagnamento_offre_il_ritorno_alla_home(client):
    resp = client.get('/iscrizione-accompagnamento/conferma')

    assert resp.status_code == 200
    assert resp.text.count('<h1>') == 1
    assert 'data-conversion="birth_private_confirmation_home"' in resp.text
    assert '>Torna alla homepage<' in resp.text


def test_admin_gestisce_percorso_accompagnamento_e_export_pdf(client):
    csrf = _login_admin(client)
    resp = client.post('/admin/percorso-accompagnamento/aggiungi', data={
        'titolo': 'Iscrizione al corso',
        'slug': 'edizione-privata-test',
        'capienza_coppie': '6',
        'stato': 'Aperto',
        'contatti': '3806317175',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        percorso = PercorsoAccompagnamento.query.filter_by(slug='edizione-privata-test').one()
        percorso_id = percorso.id

    csrf = _csrf_admin(client)
    resp = client.post(f'/admin/percorso-accompagnamento/{percorso_id}/incontro/aggiungi', data={
        'numero': '1',
        'data': '2099-09-01',
        'ora': '17:00',
        'professionista': 'Ostetrica',
        'tema': 'Nascita e rientro a casa',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        percorso = db.session.get(PercorsoAccompagnamento, percorso_id)
        persona = PersonaCorso(nome='Luisa Verdi', telefono='3331234567', email='luisa@example.com')
        iscrizione = IscrizioneCorso(
            percorso_accompagnamento=percorso,
            persona=persona,
            corso_tipo='accompagnamento-nascita',
            corso_titolo=percorso.titolo,
            nome='Luisa Verdi',
            telefono='3331234567',
            email='luisa@example.com',
            codice_fiscale='VRDLSU90A41G482Y',
            data_corso='Percorso di 1 incontri',
            partecipazione='Coppia - partner si',
            dati_extra='{"data_presunta_parto": "2100-01-10", "partner_presente": "Si"}',
            tipo_richiesta='iscrizione_effettiva',
            posti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        db.session.add_all([persona, iscrizione])
        db.session.commit()
        iscrizione_id = iscrizione.id
        incontro_id = IncontroAccompagnamento.query.filter_by(percorso_id=percorso_id).one().id

    csrf = _csrf_admin(client)
    resp = client.post(f'/admin/percorso-accompagnamento/{percorso_id}/presenze', data={
        f'presenza_{iscrizione_id}_{incontro_id}': 'presente',
        '_csrf_token': csrf,
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        presenza = PresenzaAccompagnamento.query.one()
        assert presenza.presente is True

    resp = client.get(f'/admin/percorso-accompagnamento/{percorso_id}/export-pdf')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert resp.data.startswith(b'%PDF')


@pytest.fixture
def google_calendar_scrittura_finto(app, monkeypatch):
    """Configura la scrittura su Google Calendar e sostituisce il client API
    reale con un mock, per verificare le chiamate senza contattare Google."""
    app_module.app.config['GOOGLE_CALENDAR_ID'] = 'finto@group.calendar.google.com'
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = '/percorso/finto/service-account.json'
    mock_servizio = MagicMock()
    mock_servizio.events.return_value.list.return_value.execute.return_value = {
        'items': [],
    }
    monkeypatch.setattr(app_module, '_ottieni_servizio_calendario', lambda: mock_servizio)
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._azzera_stato_calendario()


def test_admin_completa_conferma_modifica_e_annullamento_call_sonno(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    data_iniziale = app_module.prima_data_call_disponibile()
    data_modificata = data_iniziale + app_module.timedelta(days=1)
    while not app_module._giorno_lavorativo_call(data_modificata):
        data_modificata += app_module.timedelta(days=1)

    with flask_app.app_context():
        call = CallSonno(
            nome='Anna Verdi',
            telefono='3331234567',
            email='anna@example.com',
            eta_bambino_mesi=7,
            difficolta_principale='Risvegli notturni frequenti',
            ruolo_richiedente='Genitore con responsabilità genitoriale',
            durata_difficolta='Da 1 a 3 mesi',
            obiettivo_call='Capire il percorso.',
            presa_visione_offerta=True,
            conferma_ambito=True,
            consenso_privacy=True,
            data=data_iniziale.isoformat(),
            ora='09:00',
            stato='In attesa',
        )
        db.session.add(call)
        db.session.commit()
        call_id = call.id

    mock_servizio.events.return_value.insert.return_value.execute.return_value = {
        'id': 'evento-call-test'
    }
    csrf = _login_admin(client)
    with patch.object(
        app_module,
        'invia_email_conferma_call_sonno',
        return_value=True,
    ):
        conferma = client.post(
            f'/admin/call-sonno/{call_id}/conferma',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )

    assert conferma.status_code == 200
    assert 'Call confermata e comunicazione inviata.' in conferma.text
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato == 'Confermata'
        assert call.google_event_id == 'evento-call-test'

    csrf = _csrf_admin(client)
    with patch.object(
        app_module,
        'invia_email_conferma_call_sonno',
        return_value=True,
    ):
        modifica = client.post(
            f'/admin/call-sonno/{call_id}/modifica',
            data={
                'data': data_modificata.isoformat(),
                'ora': '09:30',
                '_csrf_token': csrf,
            },
            follow_redirects=True,
        )

    assert modifica.status_code == 200
    assert 'Nuovo orario confermato e comunicato alla famiglia.' in modifica.text
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.data == data_modificata.isoformat()
        assert call.ora == '09:30'
        assert call.stato == 'Confermata'
    mock_servizio.events.return_value.patch.assert_called()

    csrf = _csrf_admin(client)
    with patch.object(
        app_module,
        'invia_email_annullamento_call_sonno',
        return_value=True,
    ):
        annulla = client.post(
            f'/admin/call-sonno/{call_id}/annulla',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )

    assert annulla.status_code == 200
    assert 'Call annullata.' in annulla.text
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato == 'Annullata'
        assert call.google_event_id is None
    mock_servizio.events.return_value.delete.assert_called_with(
        calendarId='finto@group.calendar.google.com',
        eventId='evento-call-test',
    )


def test_admin_call_avvisa_se_email_fallisce_ma_calendar_riesce(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {
        'id': 'evento-call-email-fallita'
    }
    with flask_app.app_context():
        call = CallSonno(
            nome='Anna Verdi',
            telefono='3331234567',
            email='anna@example.com',
            eta_bambino_mesi=7,
            difficolta_principale='Risvegli notturni frequenti',
            ruolo_richiedente='Genitore con responsabilità genitoriale',
            durata_difficolta='Da 1 a 3 mesi',
            obiettivo_call='Capire il percorso.',
            presa_visione_offerta=True,
            conferma_ambito=True,
            consenso_privacy=True,
            data=app_module.prima_data_call_disponibile().isoformat(),
            ora='09:00',
            stato='In attesa',
        )
        db.session.add(call)
        db.session.commit()
        call_id = call.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post(
            f'/admin/call-sonno/{call_id}/conferma',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert 'Call confermata e Calendar aggiornato, ma l’email non è partita.' in resp.text
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato == 'Confermata'
        assert call.google_event_id == 'evento-call-email-fallita'
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='CallSonno',
            entita_id=call_id,
        ).one()
        assert evento.esito == 'errore'


def test_admin_offerta_pagamento_e_questionario_sonno(client, app, monkeypatch):
    monkeypatch.setitem(app.config, 'BONIFICO_INTESTATARIO', 'S.C. Studio Infermieristico')
    monkeypatch.setitem(app.config, 'BONIFICO_IBAN', 'IT00X0000000000000000000000')
    with flask_app.app_context():
        call = CallSonno(
            nome='Anna Verdi',
            telefono='3331234567',
            email='anna@example.com',
            eta_bambino_mesi=7,
            difficolta_principale='Risvegli notturni frequenti',
            ruolo_richiedente='Genitore con responsabilità genitoriale',
            durata_difficolta='Da 1 a 3 mesi',
            obiettivo_call='Capire il percorso.',
            presa_visione_offerta=True,
            conferma_ambito=True,
            consenso_privacy=True,
            data=app_module.prima_data_call_disponibile().isoformat(),
            ora='09:00',
            stato='Confermata',
        )
        db.session.add(call)
        db.session.commit()
        call_id = call.id

    csrf = _login_admin(client)
    with patch.object(
        app_module,
        'invia_email_offerta_sonno',
        return_value=True,
    ) as invio_offerta:
        resp = client.post(
            f'/admin/call-sonno/{call_id}/offerta',
            data={
                '_csrf_token': csrf,
                'azione': 'crea',
                'proposta_tipo': 'percorso',
            },
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert 'Proposta privata generata e inviata' in resp.text
    invio_offerta.assert_called_once()
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato == 'Conclusa'
        assert call.proposta_tipo == 'percorso'
        assert call.proposta_token
        assert call.proposta_scade_il - call.proposta_inviata_il == app_module.timedelta(days=7)
        proposal_token = call.proposta_token

    offer = client.get(f'/offerta-sonno/{proposal_token}')
    assert offer.status_code == 200
    assert 'Percorso sonno personalizzato' in offer.text
    assert 'Percorso sonno con affiancamento' in offer.text
    assert 'Se non selezioni la seconda casella' in offer.text
    assert 'Conferma la scelta della modalità di pagamento' in offer.text
    assert 'Conferma l’acquisto con obbligo di pagamento' not in offer.text
    assert 'Formula, prezzo e dichiarazioni vengono registrati' not in offer.text
    offer_csrf = re.search(r'name="_csrf_token" value="([^"]+)"', offer.text).group(1)

    missing_terms = client.post(
        f'/offerta-sonno/{proposal_token}',
        data={
            '_csrf_token': offer_csrf,
            'formula_scelta': 'affiancamento',
            'metodo_pagamento': 'bonifico',
        },
    )
    assert missing_terms.status_code == 400
    assert 'Devi dichiarare di aver letto e accettato' in missing_terms.text

    offer_csrf = re.search(r'name="_csrf_token" value="([^"]+)"', missing_terms.text).group(1)
    accepted = client.post(
        f'/offerta-sonno/{proposal_token}',
        data={
            '_csrf_token': offer_csrf,
            'formula_scelta': 'affiancamento',
            'metodo_pagamento': 'bonifico',
            'condizioni_sonno': 'on',
            'avvio_anticipato': 'on',
        },
    )
    assert accepted.status_code == 302
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.formula_scelta == 'affiancamento'
        assert call.prezzo_centesimi == 32000
        assert call.stato_pagamento == 'In attesa'
        assert call.condizioni_versione == '2026-08-31'
        assert call.condizioni_accettate_il is not None
        assert call.avvio_anticipato is True
        assert call.avvio_anticipato_accettato_il is not None
        assert call.pagamento_confermato_il is None

    bank_summary = client.get(f'/offerta-sonno/{proposal_token}')
    assert 'IT00X0000000000000000000000' in bank_summary.text
    assert 'Percorso sonno con affiancamento - Verdi' in bank_summary.text
    assert 'Cambia la modalità di pagamento' in bank_summary.text
    assert 'name="metodo_pagamento"' not in bank_summary.text

    edit_payment = client.get(f'/offerta-sonno/{proposal_token}?modifica=1')
    assert 'name="metodo_pagamento"' in edit_payment.text
    assert 'Conferma la scelta della modalità di pagamento' in edit_payment.text

    detail = client.get(f'/admin/pratica/CallSonno/{call_id}')
    assert 'Rimborso teorico oggi' not in detail.text
    assert 'rimborso base' not in detail.text
    admin_csrf = re.search(r'name="_csrf_token" value="([^"]+)"', detail.text).group(1)
    with patch.object(
        app_module,
        'invia_email_questionario_sonno',
        return_value=True,
    ) as invio_questionario:
        confirmed = client.post(
            f'/admin/call-sonno/{call_id}/conferma-pagamento',
            data={
                '_csrf_token': admin_csrf,
                'riferimento_pagamento': 'BONIFICO-TEST-001',
            },
            follow_redirects=True,
        )

    assert confirmed.status_code == 200
    assert 'Pagamento confermato. Riepilogo, condizioni e questionario inviati.' in confirmed.text
    invio_questionario.assert_called_once()
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato_pagamento == 'Confermato'
        assert call.pagamento_confermato_il is not None
        assert call.riferimento_pagamento == 'BONIFICO-TEST-001'
        assert call.token_questionario
        assert call.questionario_inviato_il is not None
        token = call.token_questionario

    questionario = client.get(f'/questionario-sonno/{token}')
    assert questionario.status_code == 200
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in questionario.text


def test_offerta_sonno_senza_avvio_anticipato_preserva_recesso_integrale(client, app, monkeypatch):
    monkeypatch.setitem(app.config, 'BONIFICO_INTESTATARIO', 'S.C. Studio Infermieristico')
    monkeypatch.setitem(app.config, 'BONIFICO_IBAN', 'IT00X0000000000000000000000')
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True, data='2026-09-21', ora='09:00', stato='Conclusa',
            proposta_tipo='mirata', proposta_token=secrets.token_urlsafe(48),
            proposta_scade_il=app_module.utc_now() + app_module.timedelta(days=7),
        )
        db.session.add(call)
        db.session.commit()
        call_id = call.id
        token = call.proposta_token

    page = client.get(f'/offerta-sonno/{token}')
    csrf = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post(
        f'/offerta-sonno/{token}',
        data={
            '_csrf_token': csrf,
            'formula_scelta': 'mirata',
            'metodo_pagamento': 'bonifico',
            'condizioni_sonno': 'on',
        },
    )

    assert response.status_code == 302
    with app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.avvio_anticipato is False
        assert call.avvio_anticipato_accettato_il is None
        assert call.condizioni_accettate_il is not None


def test_avvio_lavoro_sonno_attende_questionario_e_recesso(app):
    pagamento = datetime(2026, 9, 1, 10, 0)
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli', consenso_privacy=True,
            data='2026-09-21', ora='09:00', formula_scelta='percorso',
            pagamento_confermato_il=pagamento, avvio_anticipato=False,
        )
        db.session.add(call)
        db.session.flush()

        assert app_module._data_avvio_lavoro_sonno(call) is None

        call.questionario = QuestionarioSonno(
            call_sonno_id=call.id,
            risposte='{}',
            consenso_dati_sanitari=True,
            compilato_il=datetime(2026, 9, 3, 9, 0),
        )
        db.session.flush()
        assert app_module._data_avvio_lavoro_sonno(call) == datetime(2026, 9, 15, 10, 0)

        call.avvio_anticipato = True
        assert app_module._data_avvio_lavoro_sonno(call) == datetime(2026, 9, 3, 9, 0)


def test_recesso_senza_avvio_anticipato_rimborsa_intero_importo(app):
    pagamento = datetime(2026, 9, 1, 10, 0)
    call = CallSonno(
        formula_scelta='mirata',
        prezzo_centesimi=7500,
        pagamento_confermato_il=pagamento,
        avvio_anticipato=False,
    )

    assert app_module._rimborso_sonno_centesimi(
        call, pagamento + app_module.timedelta(days=13),
    ) == 7500
    assert app_module._rimborso_sonno_centesimi(
        call, pagamento + app_module.timedelta(days=14),
    ) is None


def test_admin_non_puo_avviare_il_percorso_prima_della_data_prevista(client, app):
    pagamento = app_module.utc_now()
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli', consenso_privacy=True,
            data='2026-09-21', ora='09:00', formula_scelta='percorso',
            prezzo_centesimi=20000, stato_pagamento='Confermato',
            pagamento_confermato_il=pagamento, avvio_anticipato=False,
        )
        db.session.add(call)
        db.session.flush()
        db.session.add(QuestionarioSonno(
            call_sonno_id=call.id,
            risposte='{}',
            consenso_dati_sanitari=True,
            compilato_il=pagamento,
        ))
        db.session.commit()
        call_id = call.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/call-sonno/{call_id}/percorso',
        data={
            '_csrf_token': csrf,
            'fase_percorso': 'diario_preparato',
            'stato_pagamento': 'Confermato',
        },
        follow_redirects=True,
    )

    assert 'Il lavoro professionale non può iniziare' in response.text
    with app.app_context():
        assert db.session.get(CallSonno, call_id).fase_percorso == 'non_avviato'


@pytest.mark.parametrize(
    ('phase', 'expected'),
    [
        ('non_avviato', 20000),
        ('diario_preparato', 15000),
        ('prima_call', 10000),
        ('seconda_call', 5000),
        ('terza_call', 0),
    ],
)
def test_rimborso_percorso_sonno_segue_la_fase(phase, expected):
    call = CallSonno(formula_scelta='percorso', fase_percorso=phase)
    assert app_module._rimborso_sonno_centesimi(call) == expected


@pytest.mark.parametrize(
    ('elapsed_days', 'expected'),
    [(0, 19000), (14, 19000), (15, 16000), (30, 13000), (45, 10000)],
)
def test_rimborso_affiancamento_somma_residuo_whatsapp(elapsed_days, expected):
    started = datetime(2026, 9, 1, 12, 0)
    call = CallSonno(
        formula_scelta='affiancamento',
        fase_percorso='prima_call',
        supporto_whatsapp_attivato_il=started,
    )
    reference = started + app_module.timedelta(days=elapsed_days)
    assert app_module._rimborso_sonno_centesimi(call, reference) == expected


def test_richieste_prestazioni_usano_trenta_minuti_prima_della_scelta_admin():
    assert app_module.DURATA_SLOT_MINUTI == 30

    for servizio in app_module.SERVIZI_PRENOTABILI:
        appuntamento = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio=servizio,
            data='2026-09-01',
            ora='10:00',
        )
        corpo = app_module._corpo_evento_da_appuntamento(appuntamento)
        inizio = datetime.fromisoformat(corpo['start']['dateTime'])
        fine = datetime.fromisoformat(corpo['end']['dateTime'])

        assert fine - inizio == app_module.timedelta(minutes=30), servizio


def test_evento_appuntamento_usa_durata_effettiva_scelta():
    appuntamento = Appuntamento(
        nome='Mario Rossi',
        telefono='3331234567',
        email='mario@example.com',
        servizio='Terapia infusionale / flebo',
        data='2026-09-01',
        ora='10:00',
        duration_minutes=75,
    )

    corpo = app_module._corpo_evento_da_appuntamento(appuntamento)
    inizio = datetime.fromisoformat(corpo['start']['dateTime'])
    fine = datetime.fromisoformat(corpo['end']['dateTime'])

    assert fine - inizio == app_module.timedelta(minutes=75)


def test_durata_effettiva_rispetta_le_chiusure_dello_studio():
    assert app_module.parse_appointment_duration('7') == 7
    assert app_module.parse_appointment_duration('0') is None
    assert app_module.parse_appointment_duration('481') is None
    assert app_module.parse_appointment_duration('non-valida') is None

    assert app_module.is_appointment_interval_bookable(
        '2026-09-01', '12:30', 30
    ) is True
    assert app_module.is_appointment_interval_bookable(
        '2026-09-01', '12:30', 35
    ) is False
    assert app_module.is_appointment_interval_bookable(
        '2026-09-01', '18:30', 30
    ) is True
    assert app_module.is_appointment_interval_bookable(
        '2026-09-01', '18:30', 60
    ) is False
    assert app_module.is_appointment_interval_bookable(
        '2026-09-05', '11:30', 30
    ) is True
    assert app_module.is_appointment_interval_bookable(
        '2026-09-05', '11:30', 35
    ) is False


def test_durata_effettiva_blocca_tutto_intervallo_nel_database(app):
    with app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Terapia infusionale / flebo',
            data='2026-09-01',
            ora='10:00',
            duration_minutes=75,
            stato='Confermato',
        )
        db.session.add(appuntamento)
        db.session.commit()

        assert app_module.slot_occupato_db('2026-09-01', '11:00', 30) is True
        assert app_module.slot_occupato_db('2026-09-01', '11:30', 30) is False


def test_conferma_crea_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Confermare un appuntamento deve creare un evento su Google Calendar e
    salvarne l'ID sull'appuntamento."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events().insert().execute.return_value = {'id': 'evento-abc-123'}

    with flask_app.app_context():
        appt = Appuntamento(
            nome='Mario Rossi',
            telefono='333',
            email='m@example.com',
            servizio='Lavaggio auricolare',
            data='2026-09-01',
            ora='10:00',
            consenso_privacy=True,
        )
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.post(
        f'/admin/aggiorna/{appt_id}/Confermato',
        data={'_csrf_token': csrf, 'duration_minutes': '75'},
    )

    mock_servizio.events().insert.assert_called()
    corpo_inviato = mock_servizio.events().insert.call_args.kwargs['body']
    assert corpo_inviato['summary'] == 'Mario Rossi Lavaggio auricolare'
    assert corpo_inviato['end']['dateTime'].startswith('2026-09-01T11:15:00')

    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.google_event_id == 'evento-abc-123'
        assert aggiornato.duration_minutes == 75
        patient = PersonaCorso.query.one()
        link = app_module.CollegamentoPersona.query.one()
        assert patient.nome == 'Mario Rossi'
        assert patient.telefono == '333'
        assert patient.email == 'm@example.com'
        assert link.persona_id == patient.id
        assert link.entita_tipo == 'Appuntamento'
        assert link.entita_id == appt_id
        consent = ConsensoPrivacyPaziente.query.one()
        assert consent.persona_id == patient.id
        assert consent.entita_tipo == 'Appuntamento'
        assert consent.entita_id == appt_id
        assert consent.accettato is True
        assert consent.accettato_il == aggiornato.creato_il


def test_conferma_appuntamento_non_unisce_pazienti_solo_per_contatti_uguali(
    client,
    google_calendar_scrittura_finto,
):
    google_calendar_scrittura_finto.events().insert().execute.return_value = {
        'id': 'evento-contatti-uguali'
    }
    with flask_app.app_context():
        existing_patient = PersonaCorso(
            nome='Mario Rossi esistente',
            telefono='3331234567',
            email='mario@example.com',
        )
        appointment = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Lavaggio auricolare',
            data='2026-09-01',
            ora='10:00',
        )
        db.session.add_all([existing_patient, appointment])
        db.session.commit()
        existing_patient_id = existing_patient.id
        appointment_id = appointment.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/aggiorna/{appointment_id}/Confermato',
        data={'_csrf_token': csrf, 'duration_minutes': '30'},
    )

    assert response.status_code == 302
    with flask_app.app_context():
        assert PersonaCorso.query.count() == 2
        link = app_module.CollegamentoPersona.query.filter_by(
            entita_tipo='Appuntamento',
            entita_id=appointment_id,
        ).one()
        assert link.persona_id != existing_patient_id
        assert link.persona.nome == 'Mario Rossi'


def test_conferma_richiede_durata_manuale(client, google_calendar_scrittura_finto):
    mock_servizio = google_calendar_scrittura_finto
    with flask_app.app_context():
        appt = Appuntamento(
            nome='Mario Rossi',
            telefono='333',
            email='m@example.com',
            servizio='Lavaggio auricolare',
            data='2026-09-01',
            ora='10:00',
        )
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/aggiorna/{appt_id}/Confermato',
        data={'_csrf_token': csrf},
        follow_redirects=True,
    )

    assert 'Indica una durata valida' in response.text
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.stato == 'In attesa'
        assert PersonaCorso.query.count() == 0
        assert app_module.CollegamentoPersona.query.count() == 0


def test_conferma_rifiuta_durata_che_invade_un_altro_appuntamento(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    with flask_app.app_context():
        appt = Appuntamento(
            nome='Mario Rossi',
            telefono='333',
            email='m@example.com',
            servizio='Terapia infusionale / flebo',
            data='2026-09-01',
            ora='10:00',
        )
        successivo = Appuntamento(
            nome='Luisa Verdi',
            telefono='334',
            email='l@example.com',
            servizio='Medicazione semplice',
            data='2026-09-01',
            ora='10:30',
        )
        db.session.add_all([appt, successivo])
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    response = client.post(
        f'/admin/aggiorna/{appt_id}/Confermato',
        data={'_csrf_token': csrf, 'duration_minutes': '60'},
        follow_redirects=True,
    )

    assert 'si sovrappone a un altro impegno' in response.text
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.stato == 'In attesa'
        assert aggiornato.duration_minutes == 30


@pytest.mark.parametrize('tipo_errore', ['http_404', 'timeout', 'ssl'])
def test_errore_calendar_non_perde_appuntamento_e_finisce_nel_registro(
    client,
    google_calendar_scrittura_finto,
    tipo_errore,
):
    mock_servizio = google_calendar_scrittura_finto
    if tipo_errore == 'http_404':
        risposta = MagicMock(status=404, reason='Not Found')
        errore = HttpError(risposta, b'{"error": "not found"}')
    elif tipo_errore == 'timeout':
        errore = TimeoutError('Calendar non disponibile')
    else:
        errore = ssl.SSLError('Calendar non disponibile')
    mock_servizio.events.return_value.insert.return_value.execute.side_effect = errore

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Lavaggio auricolare', data='2026-09-01', ora='10:00')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.post(
        f'/admin/aggiorna/{appt_id}/Confermato',
        data={'_csrf_token': csrf, 'duration_minutes': '30'},
    )

    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        evento = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
            entita_tipo='Appuntamento',
            entita_id=appt_id,
        ).one()
        assert aggiornato.stato == 'Confermato'
        assert aggiornato.google_event_id is None
        link = app_module.CollegamentoPersona.query.filter_by(
            entita_tipo='Appuntamento',
            entita_id=appt_id,
        ).one()
        assert link.persona.nome == 'Mario Rossi'
        assert 'sincronizzazione' in evento.messaggio

    admin_resp = client.get('/admin')
    assert admin_resp.status_code == 200
    assert client.get('/healthz').status_code == 200
    assert 'Registro eventi' in admin_resp.text
    assert 'email e Google Calendar non sono stati aggiornati' in admin_resp.text


def test_admin_appuntamento_avvisa_se_email_fallisce_ma_calendar_riesce(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {
        'id': 'evento-appuntamento-email-fallita'
    }
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Lavaggio auricolare',
            data='2026-09-01',
            ora='10:00',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post(
            f'/admin/aggiorna/{appuntamento_id}/Confermato',
            data={
                '_csrf_token': csrf,
                'duration_minutes': '30',
            },
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert (
        'Appuntamento confermato e Google Calendar aggiornato, '
        'ma l’email non è partita.'
    ) in resp.text
    with flask_app.app_context():
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        assert appuntamento.stato == 'Confermato'
        assert appuntamento.google_event_id == 'evento-appuntamento-email-fallita'
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='Appuntamento',
            entita_id=appuntamento_id,
        ).one()
        assert evento.esito == 'errore'


def test_annullamento_elimina_evento_da_calendario(client, google_calendar_scrittura_finto):
    """Annullare un appuntamento già confermato deve eliminare l'evento da
    Google Calendar e ripulire il riferimento salvato."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato', google_event_id='evento-da-eliminare')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.post(f'/admin/aggiorna/{appt_id}/Annullato', data={'_csrf_token': csrf})

    mock_servizio.events().delete.assert_called_with(
        calendarId='finto@group.calendar.google.com', eventId='evento-da-eliminare'
    )
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.google_event_id is None


def test_spostamento_aggiorna_evento_esistente(client, google_calendar_scrittura_finto):
    """Spostare un appuntamento già collegato a un evento deve aggiornarlo
    (patch) invece di crearne uno nuovo."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato', google_event_id='evento-esistente')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    client.post(f'/admin/modifica/{appt_id}', data={
        'data': '2026-09-02', 'ora': '11:00',
        'duration_minutes': '45', '_csrf_token': csrf
    })

    mock_servizio.events().patch.assert_called_once()
    kwargs = mock_servizio.events().patch.call_args.kwargs
    assert kwargs['eventId'] == 'evento-esistente'
    assert kwargs['body']['end']['dateTime'].startswith('2026-09-02T11:45:00')
    mock_servizio.events().insert.assert_not_called()


def test_aggiunta_corso_crea_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Creare un corso in admin deve creare anche l'evento Google Calendar."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {'id': 'evento-corso-123'}

    csrf = _login_admin(client)
    client.post('/admin/corso/aggiungi', data={
        'tipo': 'disostruzione-pediatrica',
        'titolo': 'Disostruzione pediatrica',
        'durata_ore': '2',
        'descrizione': 'Manovre salvavita per genitori e famiglie',
        'data': '2026-09-10',
        'ora': '18:00',
        'luogo': 'Studio infermieristico',
        '_csrf_token': csrf,
    })

    mock_servizio.events().insert.assert_called_once()
    kwargs = mock_servizio.events().insert.call_args.kwargs
    assert kwargs['calendarId'] == 'finto@group.calendar.google.com'
    assert kwargs['body']['summary'] == 'Corso: Disostruzione pediatrica'
    assert kwargs['body']['location'] == 'Studio infermieristico'
    assert kwargs['body']['start']['dateTime'].startswith('2026-09-10T18:00:00')
    assert kwargs['body']['end']['dateTime'].startswith('2026-09-10T20:00:00')

    with flask_app.app_context():
        corso = Corso.query.filter_by(titolo='Disostruzione pediatrica').one()
        assert corso.tipo == 'disostruzione-pediatrica'
        assert corso.durata_ore == 2
        assert corso.google_event_id == 'evento-corso-123'


def test_aggiunta_corso_usa_durata_modificata_su_calendario(client, google_calendar_scrittura_finto):
    """La durata modificabile nel form admin determina l'orario di fine su Calendar."""
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {'id': 'evento-blsd-123'}

    csrf = _login_admin(client)
    client.post('/admin/corso/aggiungi', data={
        'tipo': 'bls-d',
        'titolo': 'BLSD aziendale',
        'durata_ore': '4',
        'descrizione': 'Corso in azienda',
        'data': '2026-09-11',
        'ora': '09:00',
        'luogo': 'Azienda',
        '_csrf_token': csrf,
    })

    kwargs = mock_servizio.events().insert.call_args.kwargs
    assert kwargs['body']['start']['dateTime'].startswith('2026-09-11T09:00:00')
    assert kwargs['body']['end']['dateTime'].startswith('2026-09-11T13:00:00')

    with flask_app.app_context():
        corso = Corso.query.filter_by(titolo='BLSD aziendale').one()
        assert corso.tipo == 'bls-d'
        assert corso.durata_ore == 4


@pytest.mark.parametrize('stato_iniziale', ['Aperto', 'Annullato'])
def test_modifica_stato_corso_annullato_avvisa_solo_i_confermati_una_volta(
    client,
    google_calendar_scrittura_finto,
    stato_iniziale,
):
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        corso = Corso(
            titolo='Disostruzione pediatrica',
            tipo='disostruzione-pediatrica',
            data='2099-11-07',
            ora='17:30',
            luogo='S.C. Studio Infermieristico',
            durata_ore=2,
            capienza_massima=8,
            stato=stato_iniziale,
            google_event_id='evento-da-annullare',
        )
        db.session.add(corso)
        db.session.flush()

        def iscrizione(nome, email, stato):
            return IscrizioneCorso(
                corso_id=corso.id,
                corso_tipo=corso.tipo,
                corso_titolo=corso.titolo,
                nome=nome,
                telefono='3331234567',
                email=email,
                codice_fiscale='RSSMRA80A01G482X',
                data_corso='07/11/2099 - ore 17:30 - S.C. Studio Infermieristico',
                partecipazione='Iscrizione individuale',
                tipo_richiesta='richiesta_iscrizione',
                posti=1 if stato == 'Confermato' else 0,
                posti_richiesti=1,
                consenso_privacy=True,
                stato=stato,
            )

        db.session.add_all([
            iscrizione('Mario Rossi', 'mario@example.com', 'Confermato'),
            iscrizione('Giulia Bianchi', 'giulia@example.com', 'Nuova'),
            iscrizione('Luca Verdi', 'luca@example.com', 'Lista attesa'),
        ])
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    dati_modifica = {
        '_csrf_token': csrf,
        'titolo': 'Disostruzione pediatrica',
        'data': '2099-11-07',
        'ora': '17:30',
        'luogo': 'S.C. Studio Infermieristico',
        'durata_ore': '2',
        'capienza_massima': '8',
        'stato': 'Annullato',
    }
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/corso/{corso_id}/modifica',
            data=dati_modifica,
            follow_redirects=True,
        )
        ripetizione = client.post(
            f'/admin/corso/{corso_id}/modifica',
            data=dati_modifica,
            follow_redirects=True,
        )

    assert resp.status_code == ripetizione.status_code == 200
    assert 'Corso annullato e partecipanti confermati avvisati via email (1).' in resp.text
    assert send_mock.call_count == 1
    messaggio = send_mock.call_args.args[0]
    assert messaggio.recipients == ['mario@example.com']
    assert messaggio.subject == 'Edizione annullata - Disostruzione pediatrica'
    assert '07/11/2099 - ore 17:30 - S.C. Studio Infermieristico' in messaggio.body
    mock_servizio.events().delete.assert_called_once_with(
        calendarId='finto@group.calendar.google.com',
        eventId='evento-da-annullare',
    )
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        corso = db.session.get(Corso, corso_id)
        assert corso.stato == 'Annullato'
        assert corso.archiviato_il is not None
        assert corso.google_event_id is None


def test_annullamento_corso_recupera_ed_elimina_evento_calendar_senza_id_locale(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        corso = Corso(
            titolo='BLSD',
            tipo='bls-d',
            data='2099-11-06',
            ora='09:00',
            luogo='S.C. Studio Infermieristico',
            durata_ore=5,
            stato='Annullato',
            google_event_id=None,
        )
        db.session.add(corso)
        db.session.commit()
        corso_id = corso.id

    mock_servizio.events.return_value.list.return_value.execute.return_value = {
        'items': [{
            'id': 'evento-remoto-recuperato',
            'extendedProperties': {'private': {
                'studioEntity': 'Corso',
                'studioEntityId': str(corso_id),
            }},
        }],
    }
    csrf = _login_admin(client)
    resp = client.post(
        f'/admin/corso/{corso_id}/modifica',
        data={
            '_csrf_token': csrf,
            'titolo': 'BLSD',
            'data': '2099-11-06',
            'ora': '09:00',
            'luogo': 'S.C. Studio Infermieristico',
            'durata_ore': '5',
            'stato': 'Annullato',
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    mock_servizio.events().list.assert_any_call(
        calendarId='finto@group.calendar.google.com',
        privateExtendedProperty=f'studioEntityId={corso_id}',
        showDeleted=False,
        maxResults=10,
    )
    mock_servizio.events().delete.assert_called_once_with(
        calendarId='finto@group.calendar.google.com',
        eventId='evento-remoto-recuperato',
    )
    with flask_app.app_context():
        corso = db.session.get(Corso, corso_id)
        assert corso.archiviato_il is not None
        assert corso.google_event_id is None
        recupero = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            entita_tipo='Corso',
            entita_id=corso_id,
        ).filter(RegistroEvento.messaggio.contains('recuperato')).one()
        assert recupero.esito == 'avviso'


def test_archiviazione_corso_elimina_evento_ma_conserva_storico(client, google_calendar_scrittura_finto):
    """Archiviare un corso cancella l'evento ma conserva la pratica."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        corso = Corso(
            titolo='Corso di accompagnamento alla nascita',
            tipo='accompagnamento-nascita',
            descrizione='Percorso in presenza',
            data='2026-09-12',
            ora='10:00',
            luogo='Studio',
            durata_ore=2,
            google_event_id='evento-corso-da-eliminare',
        )
        db.session.add(corso)
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    client.post(f'/admin/corso/elimina/{corso_id}', data={'_csrf_token': csrf})

    mock_servizio.events().delete.assert_called_once_with(
        calendarId='finto@group.calendar.google.com',
        eventId='evento-corso-da-eliminare',
    )
    with flask_app.app_context():
        corso = db.session.get(Corso, corso_id)
        assert corso is not None
        assert corso.archiviato_il is not None
        assert corso.stato == 'Annullato'


@pytest.mark.parametrize(
    ('tipo', 'titolo'),
    [
        ('disostruzione-pediatrica', 'Disostruzione pediatrica'),
        ('laboratorio-infanzia', 'Laboratorio gioco e sviluppo'),
    ],
)
def test_archiviazione_edizione_avvisa_solo_i_partecipanti_confermati(
    client,
    google_calendar_scrittura_finto,
    tipo,
    titolo,
):
    with flask_app.app_context():
        corso = Corso(
            titolo=titolo,
            tipo=tipo,
            data='2099-11-08',
            ora='17:30',
            luogo='S.C. Studio Infermieristico',
            durata_ore=2,
            google_event_id=f'evento-{tipo}',
        )
        db.session.add(corso)
        db.session.flush()

        def iscrizione(nome, email, stato='Confermato', archiviata_il=None):
            return IscrizioneCorso(
                corso_id=corso.id,
                corso_tipo=tipo,
                corso_titolo=titolo,
                nome=nome,
                telefono='3331234567',
                email=email,
                codice_fiscale='RSSMRA80A01G482X',
                data_corso='08/11/2099 - ore 17:30 - S.C. Studio Infermieristico',
                partecipazione='Iscrizione individuale',
                tipo_richiesta='richiesta_iscrizione',
                posti=1,
                posti_richiesti=1,
                consenso_privacy=True,
                stato=stato,
                archiviata_il=archiviata_il,
            )

        db.session.add_all([
            iscrizione('Mario Rossi', 'mario@example.com'),
            iscrizione('Giulia Bianchi', ''),
            iscrizione('Luca Verdi', 'luca@example.com', stato='Nuova'),
            iscrizione(
                'Anna Neri',
                'anna@example.com',
                archiviata_il=app_module.utc_now(),
            ),
        ])
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/corso/elimina/{corso_id}',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )
        ripetizione = client.post(
            f'/admin/corso/elimina/{corso_id}',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )

    assert resp.status_code == ripetizione.status_code == 200
    assert send_mock.call_count == 1
    messaggio = send_mock.call_args.args[0]
    assert messaggio.recipients == ['mario@example.com']
    assert messaggio.subject == f'Edizione annullata - {titolo}'
    assert f'l’edizione di {titolo}' in messaggio.body
    assert '08/11/2099 - ore 17:30 - S.C. Studio Infermieristico' in messaggio.body
    assert 'Telefono: 380 631 7175' in messaggio.body
    assert 'Email: info@scstudioinfermieristico.it' in messaggio.body
    assert 'Email inviate: 1; email non inviate: 0; email mancanti: 1.' in resp.text
    assert 'Edizione già archiviata; nessuna nuova email inviata.' in ripetizione.text


def test_errore_email_annullamento_edizione_non_ripristina_il_corso(
    client,
    google_calendar_scrittura_finto,
):
    with flask_app.app_context():
        corso = Corso(
            titolo='Laboratorio movimento',
            tipo='laboratorio-infanzia',
            data='2099-11-09',
            ora='10:00',
            luogo='S.C. Studio Infermieristico',
            durata_ore=2,
            google_event_id='evento-laboratorio',
        )
        db.session.add(corso)
        db.session.flush()
        iscrizione = IscrizioneCorso(
            corso_id=corso.id,
            corso_tipo=corso.tipo,
            corso_titolo=corso.titolo,
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='09/11/2099 - ore 10:00 - S.C. Studio Infermieristico',
            partecipazione='Iscrizione individuale',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        db.session.add(iscrizione)
        db.session.commit()
        corso_id = corso.id
        iscrizione_id = iscrizione.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send', side_effect=RuntimeError('SMTP non disponibile')):
        resp = client.post(
            f'/admin/corso/elimina/{corso_id}',
            data={'_csrf_token': csrf},
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert 'Email inviate: 0; email non inviate: 1; email mancanti: 0.' in resp.text
    with flask_app.app_context():
        corso = db.session.get(Corso, corso_id)
        assert corso.stato == 'Annullato'
        assert corso.archiviato_il is not None
        email = EmailOperativa.query.filter_by(
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione_id,
        ).one()
        assert email.stato == 'fallita'
        evento = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione_id,
        ).one()
        assert 'annullamento corso' in evento.messaggio


def test_modifica_edizione_invia_recapiti_corretti_ai_partecipanti(
    client,
    google_calendar_scrittura_finto,
):
    with flask_app.app_context():
        corso = Corso(
            titolo='Laboratorio gioco e sviluppo',
            tipo='laboratorio-infanzia',
            data='2099-11-10',
            ora='16:00',
            luogo='S.C. Studio Infermieristico',
            durata_ore=2,
            stato='Aperto',
            google_event_id='evento-laboratorio',
        )
        db.session.add(corso)
        db.session.flush()
        iscrizione = IscrizioneCorso(
            corso_id=corso.id,
            corso_tipo=corso.tipo,
            corso_titolo=corso.titolo,
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='10/11/2099 - ore 16:00 - S.C. Studio Infermieristico',
            partecipazione='Iscrizione individuale',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        db.session.add(iscrizione)
        db.session.add_all([
            IscrizioneCorso(
                corso_id=corso.id,
                corso_tipo=corso.tipo,
                corso_titolo=corso.titolo,
                nome='Luisa Verdi',
                telefono='3337654321',
                email='luisa@example.com',
                codice_fiscale='VRDLSU90A41G482Y',
                data_corso='10/11/2099 - ore 16:00 - S.C. Studio Infermieristico',
                partecipazione='Iscrizione individuale',
                tipo_richiesta='richiesta_iscrizione',
                posti=0,
                posti_richiesti=1,
                consenso_privacy=True,
                stato='Lista attesa',
            ),
            IscrizioneCorso(
                corso_id=corso.id,
                corso_tipo=corso.tipo,
                corso_titolo=corso.titolo,
                nome='Anna Neri',
                telefono='3339876543',
                email='anna@example.com',
                codice_fiscale='NRENNA90A41G482U',
                data_corso='10/11/2099 - ore 16:00 - S.C. Studio Infermieristico',
                partecipazione='Iscrizione individuale',
                tipo_richiesta='richiesta_iscrizione',
                posti=0,
                posti_richiesti=1,
                consenso_privacy=True,
                stato='Invitato',
            ),
        ])
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    dettaglio = client.get(f'/admin/pratica/Corso/{corso_id}')
    anteprima_destinatari = dettaglio.text.split('admin-recipient-preview', 1)[1].split('</div>', 1)[0]
    assert 'Destinatari aggiornamento (1)' in anteprima_destinatari
    assert 'mario@example.com' in anteprima_destinatari
    assert 'luisa@example.com' not in anteprima_destinatari
    assert 'anna@example.com' not in anteprima_destinatari
    assert 'le modifiche al corso vengono comunque salvate' in anteprima_destinatari
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/corso/{corso_id}/modifica',
            data={
                '_csrf_token': csrf,
                'titolo': 'Laboratorio gioco e sviluppo',
                'data': '2099-11-17',
                'ora': '17:00',
                'luogo': 'S.C. Studio Infermieristico',
                'durata_ore': '2',
                'capienza_massima': '8',
                'stato': 'Aperto',
                'conferma_notifiche': '1',
            },
        )

    assert resp.status_code == 302
    assert send_mock.call_count == 1
    messaggio = send_mock.call_args.args[0]
    assert messaggio.recipients == ['mario@example.com']
    assert messaggio.subject == 'Aggiornamento · Laboratorio gioco e sviluppo'
    assert 'Data e luogo: 17/11/2099 - ore 17:00 - S.C. Studio Infermieristico' in messaggio.body
    assert 'Telefono: 380 631 7175' in messaggio.body
    assert 'Email: info@scstudioinfermieristico.it' in messaggio.body


def test_modifica_ora_corso_salva_senza_destinatari_selezionati(
    client,
    google_calendar_scrittura_finto,
):
    with flask_app.app_context():
        corso = Corso(
            titolo='Corso BLSD',
            tipo='bls-d',
            data='2099-11-10',
            ora='16:00',
            luogo='S.C. Studio Infermieristico',
            durata_ore=5,
            stato='Aperto',
            google_event_id='evento-blsd',
        )
        db.session.add(corso)
        db.session.flush()
        db.session.add(IscrizioneCorso(
            corso_id=corso.id,
            corso_tipo=corso.tipo,
            corso_titolo=corso.titolo,
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='10/11/2099 - ore 16:00 - S.C. Studio Infermieristico',
            partecipazione='Iscrizione individuale',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Confermato',
        ))
        db.session.commit()
        corso_id = corso.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/corso/{corso_id}/modifica',
            data={
                '_csrf_token': csrf,
                'titolo': 'Corso BLSD',
                'data': '2099-11-10',
                'ora': '17:30',
                'luogo': 'S.C. Studio Infermieristico',
                'durata_ore': '5',
                'capienza_massima': '8',
                'stato': 'Aperto',
            },
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert 'Corso aggiornato; nessuna email inviata ai partecipanti.' in resp.text
    send_mock.assert_not_called()
    with flask_app.app_context():
        corso = db.session.get(Corso, corso_id)
        assert corso.ora == '17:30'


def test_posto_liberato_crea_contatto_telefonico_senza_email_alla_lista_attesa(client):
    corso_id = _crea_data_corso(
        'disostruzione-pediatrica',
        'Disostruzione pediatrica',
        capienza_massima=1,
    )
    with flask_app.app_context():
        confermata = IscrizioneCorso(
            corso_id=int(corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            codice_fiscale='RSSMRA80A01G482X',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=1,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Confermato',
        )
        attesa = IscrizioneCorso(
            corso_id=int(corso_id),
            corso_tipo='disostruzione-pediatrica',
            corso_titolo='Disostruzione pediatrica',
            nome='Luisa Verdi',
            telefono='3337654321',
            email='luisa@example.com',
            codice_fiscale='VRDLSU90A41G482Y',
            data_corso='16/07/2099',
            partecipazione='Singolo 34 euro',
            tipo_richiesta='richiesta_iscrizione',
            posti=0,
            posti_richiesti=1,
            consenso_privacy=True,
            stato='Lista attesa',
        )
        db.session.add_all([confermata, attesa])
        db.session.commit()
        confermata_id = confermata.id
        attesa_id = attesa.id

    csrf = _login_admin(client)
    with patch.object(app_module.mail, 'send') as send_mock:
        resp = client.post(
            f'/admin/iscrizione-corso/{confermata_id}/Annullato',
            data={'_csrf_token': csrf},
        )

    assert resp.status_code == 302
    assert send_mock.call_count == 1
    assert send_mock.call_args.args[0].recipients == ['mario@example.com']
    with flask_app.app_context():
        attesa = db.session.get(IscrizioneCorso, attesa_id)
        assert attesa.stato == 'Lista attesa'
        assert attesa.invito_lista_attesa_il is None
        assert attesa.scadenza_invito_lista_attesa is None
        attivita = app_module.AttivitaAdmin.query.filter_by(
            entita_tipo='IscrizioneCorso',
            entita_id=attesa_id,
            stato='Aperta',
        ).one()
        assert 'Contattare Luisa Verdi' in attivita.titolo
        assert 'Contatto telefonico' in attivita.note


def test_spostamento_rifiuta_orario_non_prenotabile(client, google_calendar_scrittura_finto):
    """Anche l'area admin deve rispettare chiusure e orari prenotabili."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    domenica = _prossimo_giorno_con_weekday(6).strftime('%Y-%m-%d')
    resp = client.post(f'/admin/modifica/{appt_id}', data={
        'data': domenica, 'ora': '10:00',
        'duration_minutes': '30', '_csrf_token': csrf
    })

    assert 'studio è chiuso' in resp.text
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.data == '2026-09-01'
        assert aggiornato.ora == '10:00'


# ─── Regia operativa area admin ───

def test_admin_espone_le_sezioni_operative_richieste(client):
    _login_admin(client)

    resp = client.get('/admin')

    assert resp.status_code == 200
    for etichetta in ['Agenda', 'Richieste', 'Corsi', 'Pazienti', 'Attività', 'Errori', 'Impostazioni']:
        assert f'<span>{etichetta}</span>' in resp.text
    assert '<span>Persone</span>' not in resp.text
    assert 'id="admin-pazienti"' in resp.text
    assert 'Nuove richieste in attesa' in resp.text
    assert 'Riconciliazione automatica: ogni ora.' in resp.text


def test_admin_crea_e_modifica_anagrafica_paziente(client):
    csrf = _login_admin(client)

    resp = client.post('/admin/paziente/aggiungi', data={
        '_csrf_token': csrf,
        'nome': 'Anna Neri',
        'telefono': '',
        'email': '',
        'codice_fiscale': 'nrena80a41g482x',
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        paziente = PersonaCorso.query.one()
        paziente_id = paziente.id
        assert paziente.codice_fiscale == 'NRENA80A41G482X'
        assert paziente.telefono is None
        assert paziente.email is None

    scheda = client.get(f'/admin/paziente/{paziente_id}')
    assert scheda.status_code == 200
    assert 'Modifica anagrafica' in scheda.text
    assert 'Telefono mancante' in scheda.text
    assert 'Email mancante' in scheda.text
    assert '/static/css/admin.css?v=5.4' in scheda.text

    csrf = _csrf_admin(client)
    resp = client.post(f'/admin/paziente/{paziente_id}/modifica', data={
        '_csrf_token': csrf,
        'nome': 'Anna Neri',
        'telefono': '3337654321',
        'email': 'anna@example.com',
        'codice_fiscale': 'NRENA80A41G482X',
        'nome_bambino': 'Leo',
        'eta_bambino': '18 mesi',
        'note': 'Preferisce essere contattata nel pomeriggio.',
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        aggiornato = db.session.get(PersonaCorso, paziente_id)
        assert aggiornato.telefono == '3337654321'
        assert aggiornato.email == 'anna@example.com'
        assert aggiornato.nome_bambino == 'Leo'
        modifica = app_module.RegistroModifica.query.filter_by(
            azione='modifica_anagrafica',
            entita_tipo='PersonaCorso',
            entita_id=paziente_id,
        ).one()
        dettagli = json.loads(modifica.dettagli)
        assert 'telefono' in dettagli['campi']
        assert 'email' in dettagli['campi']
        assert 'anna@example.com' not in modifica.dettagli


def test_admin_pazienti_filtra_anagrafica_e_mantiene_ricerca_pratiche(client):
    with flask_app.app_context():
        db.session.add_all([
            PersonaCorso(nome='Anna Neri', telefono='3331234567', email='anna@example.com'),
            PersonaCorso(nome='Giulia Bianchi', telefono='3337654321', email='giulia@example.com'),
            Appuntamento(
                nome='Anna Neri',
                telefono='3331234567',
                email='anna@example.com',
                servizio='Medicazione semplice',
                data='2099-09-01',
                ora='10:00',
            ),
        ])
        db.session.commit()

    _login_admin(client)
    resp = client.get('/admin?q=Anna')

    assert resp.status_code == 200
    sezione_pazienti = resp.text.split('id="admin-pazienti"', 1)[1].split('</section>', 1)[0]
    assert 'Pazienti trovati per “Anna”' in sezione_pazienti
    assert 'Anna Neri' in sezione_pazienti
    assert 'Giulia Bianchi' not in sezione_pazienti
    assert 'Pratiche trovate' in sezione_pazienti
    assert 'Medicazione semplice' in sezione_pazienti


def test_admin_crea_paziente_da_pratica_e_collega_lo_storico(client):
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            servizio='Medicazione semplice',
            data='2099-09-01',
            ora='10:00',
            consenso_privacy=True,
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id

    csrf = _login_admin(client)
    resp = client.post(
        f'/admin/pratica/Appuntamento/{appuntamento_id}/crea-paziente',
        data={'_csrf_token': csrf},
    )

    assert resp.status_code == 302
    with flask_app.app_context():
        paziente = PersonaCorso.query.one()
        collegamento = app_module.CollegamentoPersona.query.one()
        assert paziente.nome == 'Mario Rossi'
        assert collegamento.persona_id == paziente.id
        assert collegamento.entita_tipo == 'Appuntamento'
        assert collegamento.entita_id == appuntamento_id
        consenso = ConsensoPrivacyPaziente.query.one()
        assert consenso.persona_id == paziente.id
        assert consenso.accettato is True
        assert consenso.accettato_il == appuntamento.creato_il
        paziente_id = paziente.id

    scheda = client.get(f'/admin/paziente/{paziente_id}')
    assert 'Pratiche collegate' in scheda.text
    assert 'Medicazione semplice' in scheda.text
    assert 'Prese visioni privacy' in scheda.text
    assert 'Presa visione registrata' in scheda.text
    assert 'Appuntamento #' in scheda.text
    assert 'Data presa visione:' in scheda.text


def test_admin_crea_appuntamento_in_attesa_con_scadenza(client):
    with flask_app.app_context():
        paziente = PersonaCorso(
            nome='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
        )
        db.session.add(paziente)
        db.session.commit()
        paziente_id = paziente.id
    csrf = _login_admin(client)

    resp = client.post('/admin/appuntamento/aggiungi', data={
        '_csrf_token': csrf,
        'persona_id': str(paziente_id),
        'nome': 'Mario Rossi',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'servizio': 'Medicazione semplice',
        'data': '2099-09-01',
        'ora': '10:00',
        'duration_minutes': '45',
        'consenso_privacy': 'on',
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        appuntamento = Appuntamento.query.one()
        assert appuntamento.stato == 'In attesa'
        assert appuntamento.creato_da_admin is True
        assert appuntamento.duration_minutes == 45
        assert appuntamento.scadenza_gestione is not None
        collegamento = app_module.CollegamentoPersona.query.one()
        assert collegamento.persona_id == paziente_id
        assert collegamento.entita_tipo == 'Appuntamento'
        assert collegamento.entita_id == appuntamento.id
        consenso = ConsensoPrivacyPaziente.query.one()
        assert consenso.persona_id == paziente_id
        assert consenso.accettato is True
        assert consenso.accettato_il == appuntamento.creato_il


def test_admin_chiede_conferma_json_se_mancano_i_contatti(client):
    csrf = _login_admin(client)

    response = client.post('/admin/appuntamento/aggiungi', data={
        '_csrf_token': csrf,
        'nome': 'Persona senza contatti',
        'telefono': '',
        'email': '',
        'servizio': 'Medicazione semplice',
        'data': '2099-09-02',
        'ora_ore': '09',
        'ora_minuti': '35',
        'duration_minutes': '40',
        'note': 'Questi dati devono restare nel modulo.',
        'confirm_missing_contacts': '0',
    }, headers={
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })

    assert response.status_code == 409
    assert response.get_json() == {
        'ok': False,
        'message': 'Mancano telefono e email. Conferma se vuoi creare comunque l’appuntamento.',
        'requires_missing_contacts_confirmation': True,
    }
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


def test_admin_crea_appuntamento_senza_contatti_dopo_conferma(client):
    csrf = _login_admin(client)

    response = client.post('/admin/appuntamento/aggiungi', data={
        '_csrf_token': csrf,
        'nome': 'Persona senza contatti',
        'telefono': '',
        'email': '',
        'servizio': 'Medicazione semplice',
        'data': '2099-09-02',
        'ora_ore': '09',
        'ora_minuti': '35',
        'duration_minutes': '40',
        'note': 'Contatto da integrare in seguito.',
        'confirm_missing_contacts': '1',
    }, headers={
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })

    assert response.status_code == 200
    assert response.get_json()['ok'] is True
    with flask_app.app_context():
        appuntamento = Appuntamento.query.one()
        assert appuntamento.telefono == ''
        assert appuntamento.email == ''
        assert appuntamento.ora == '09:35'
        assert appuntamento.note == 'Contatto da integrare in seguito.'
        modifica = app_module.RegistroModifica.query.filter_by(
            azione='creazione_admin',
            entita_tipo='Appuntamento',
            entita_id=appuntamento.id,
        ).one()
        assert 'telefono' in modifica.dettagli
        assert 'email' in modifica.dettagli


def test_admin_non_accetta_contatto_compilato_ma_non_valido(client):
    csrf = _login_admin(client)

    response = client.post('/admin/appuntamento/aggiungi', data={
        '_csrf_token': csrf,
        'nome': 'Persona con telefono errato',
        'telefono': 'abc',
        'email': '',
        'servizio': 'Medicazione semplice',
        'data': '2099-09-02',
        'ora_ore': '09',
        'ora_minuti': '40',
        'duration_minutes': '30',
        'confirm_missing_contacts': '1',
    }, headers={
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })

    assert response.status_code == 422
    assert 'telefono inserito non è valido' in response.get_json()['message']
    with flask_app.app_context():
        assert Appuntamento.query.count() == 0


def test_admin_nuovo_appuntamento_usa_calendario_e_select_ora(client):
    _login_admin(client)

    response = client.get('/admin?vista=giorno')

    assert response.status_code == 200
    assert 'id="admin-new-appointment-form"' in response.text
    assert 'id="admin-appointment-date" name="data" type="date"' in response.text
    assert 'data-open-date-picker' in response.text
    assert 'name="ora_ore"' in response.text
    assert 'name="ora_minuti"' in response.text
    assert '<option value="55">55</option>' in response.text


def test_filtri_archivio_appuntamenti_mantengono_aperto_il_pannello(client):
    _login_admin(client)

    response = client.get('/admin?filtro=confermati')

    assert response.status_code == 200
    for filtro in ('in_attesa', 'confermati', 'annullati', 'passati'):
        assert f'href="/admin?filtro={filtro}#admin-prenotazioni"' in response.text


def test_limite_online_accetta_coppia_a_tredici_ma_non_prenota_da_quattordici(app):
    with flask_app.app_context():
        corso = Corso(titolo='Disostruzione', tipo='disostruzione-pediatrica', data='2099-09-01', capienza_massima=14)
        db.session.add(corso)
        db.session.flush()
        db.session.add(IscrizioneCorso(
            corso_id=corso.id, corso_tipo=corso.tipo, corso_titolo=corso.titolo,
            nome='Gruppo esistente', telefono='3331234567', email='', codice_fiscale='',
            posti=13, posti_richiesti=13, consenso_privacy=True, stato='Nuova',
        ))
        db.session.commit()

        assert app_module._corso_accetta_prenotazione_online(corso, 2) is True
        assert app_module._corso_accetta_prenotazione_online(corso, 1) is True
        db.session.add(IscrizioneCorso(
            corso_id=corso.id, corso_tipo=corso.tipo, corso_titolo=corso.titolo,
            nome='Quattordicesima persona', telefono='3337654321', email='', codice_fiscale='',
            posti=1, posti_richiesti=1, consenso_privacy=True, stato='Nuova',
        ))
        db.session.commit()

        assert app_module._corso_accetta_prenotazione_online(corso, 1) is False
        assert app_module._corso_accetta_prenotazione_online(corso, 2) is False


def test_admin_supera_limite_online_solo_con_conferma_e_motivo(client):
    with flask_app.app_context():
        corso = Corso(titolo='Corso pieno', tipo='bls-d', data='2099-09-01', capienza_massima=1)
        db.session.add(corso)
        db.session.flush()
        db.session.add(IscrizioneCorso(
            corso_id=corso.id, corso_tipo=corso.tipo, corso_titolo=corso.titolo,
            nome='Coppia esistente', telefono='3331234567', email='', codice_fiscale='',
            posti=2, posti_richiesti=2, consenso_privacy=True, stato='Confermato',
        ))
        db.session.commit()
        corso_id = corso.id
    csrf = _login_admin(client)
    dati = {
        '_csrf_token': csrf, 'corso_id': str(corso_id), 'nome': 'Persona extra',
        'telefono': '3337654321', 'email': 'extra@example.com', 'posti': '1',
        'partecipazione': 'Singolo', 'tipo_richiesta': 'iscrizione_effettiva', 'stato': 'Confermato',
    }

    client.post('/admin/iscrizione-corso/aggiungi', data=dati)
    with flask_app.app_context():
        assert IscrizioneCorso.query.filter_by(nome='Persona extra').count() == 0

    csrf = _csrf_admin(client)
    dati.update({
        '_csrf_token': csrf,
        'conferma_superamento_capienza': '1',
        'superamento_capienza_motivo': 'Partecipante aggiunto direttamente dallo studio',
    })
    client.post('/admin/iscrizione-corso/aggiungi', data=dati)
    with flask_app.app_context():
        extra = IscrizioneCorso.query.filter_by(nome='Persona extra').one()
        assert 'direttamente' in extra.superamento_capienza_motivo


def test_riconciliazione_segnala_modifica_esterna_senza_cambiare_appuntamento(
    app,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi', telefono='3331234567', email='mario@example.com',
            servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', google_event_id='evento-esterno',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
    mock_servizio.events.return_value.get.return_value.execute.return_value = {
        'id': 'evento-esterno',
        'summary': 'Titolo modificato fuori dal sito',
        'start': {'dateTime': '2099-09-01T10:00:00+02:00'},
        'end': {'dateTime': '2099-09-01T10:30:00+02:00'},
    }

    with flask_app.app_context():
        risultato = app_module.riconcilia_calendario()
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        assert risultato['difformi'] == 1
        assert appuntamento.sincronizzazione == 'difforme'
        assert appuntamento.servizio == 'Medicazione semplice'
        assert 'Titolo modificato' in appuntamento.difformita_calendario
        assert RegistroEvento.query.filter_by(categoria='riconciliazione_calendar').count() == 1


def test_riconciliazione_tratta_status_cancelled_come_eliminazione_esterna(
    app,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi', telefono='3331234567', email='mario@example.com',
            servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', google_event_id='evento-cancellato',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
    mock_servizio.events.return_value.get.return_value.execute.return_value = {
        'id': 'evento-cancellato',
        'status': 'cancelled',
        'summary': 'Mario Rossi Medicazione semplice',
        'start': {'dateTime': '2099-09-01T10:00:00+02:00'},
        'end': {'dateTime': '2099-09-01T10:30:00+02:00'},
    }

    with flask_app.app_context():
        risultato = app_module.riconcilia_calendario()
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        anomalia = RegistroEvento.query.filter_by(
            categoria='riconciliazione_calendar',
            entita_tipo='Appuntamento',
            entita_id=appuntamento_id,
            risolto_il=None,
        ).one()

    assert risultato['mancanti'] == 1
    assert appuntamento.stato == 'Confermato'
    assert appuntamento.google_event_id == 'evento-cancellato'
    assert appuntamento.sincronizzazione == 'eliminato_esternamente'
    assert anomalia.dettagli_dict() == {
        'evento': {'sito': 'presente', 'calendar': 'eliminato'}
    }


def test_controllo_admin_usa_finestra_di_freschezza(app, monkeypatch):
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar-test')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', '/tmp/finto.json')
    monkeypatch.setitem(app.config, 'CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI', 180)
    app_module._azzera_stato_calendario()

    with patch.object(
        app_module,
        'riconcilia_calendario',
        return_value={'controllati': 1, 'difformi': 0, 'mancanti': 0, 'errore': None},
    ) as riconcilia:
        primo = app_module._riconciliazione_admin_se_necessaria(1000)
        secondo = app_module._riconciliazione_admin_se_necessaria(1100)
        terzo = app_module._riconciliazione_admin_se_necessaria(1300)

    assert primo is not None
    assert secondo is None
    assert terzo is not None
    assert riconcilia.call_count == 2


def test_admin_mostra_modal_prioritario_e_decidi_dopo_conserva_conflitto(client):
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Test Calendar', telefono='3331234567', email='test@example.com',
            servizio='Lavaggio auricolare', data='2099-09-01', ora='09:00',
            duration_minutes=30, stato='Confermato', sincronizzazione='difforme',
            google_event_id='evento-difforme',
            difformita_calendario=json.dumps({
                'inizio': {
                    'sito': '2099-09-01T09:00+02:00',
                    'calendar': '2099-09-01T10:00+02:00',
                },
                'fine': {
                    'sito': '2099-09-01T09:30+02:00',
                    'calendar': '2099-09-01T10:30+02:00',
                },
            }),
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
        app_module._registra_anomalia_sync(
            'Appuntamento',
            appuntamento_id,
            'Evento Calendar modificato esternamente: serve conferma.',
            json.loads(appuntamento.difformita_calendario),
        )

    csrf = _login_admin(client)
    pagina = client.get('/admin')

    assert pagina.status_code == 200
    assert 'data-calendar-conflict-modal data-open-on-load' in pagina.text
    assert 'Test Calendar' in pagina.text
    assert 'Lavaggio auricolare' in pagina.text
    assert 'Accetta data e orario Calendar' in pagina.text
    assert 'Si chiude soltanto dopo una scelta nella pratica.' in pagina.text
    assert 'name="nota_risoluzione"' not in pagina.text

    risposta = client.post(
        '/admin/calendar/decidi-dopo',
        data={'_csrf_token': csrf},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert 'data-calendar-conflict-modal data-open-on-load' not in risposta.text
    assert 'Google Calendar è stato modificato' in risposta.text
    with flask_app.app_context():
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        assert appuntamento.sincronizzazione == 'difforme'
        assert RegistroEvento.query.filter_by(risolto_il=None).count() == 1


def test_ripristino_evento_eliminato_crea_nuovo_id_senza_email(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {
        'id': 'evento-ripristinato',
    }
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Test Ripristino', telefono='3331234567', email='test@example.com',
            servizio='Lavaggio auricolare', data='2099-09-01', ora='09:00',
            duration_minutes=30, stato='Confermato',
            sincronizzazione='eliminato_esternamente',
            google_event_id='evento-eliminato',
            difformita_calendario=json.dumps({
                'evento': {'sito': 'presente', 'calendar': 'eliminato'}
            }),
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
        app_module._registra_anomalia_sync(
            'Appuntamento', appuntamento_id,
            'Evento collegato eliminato da Google Calendar.',
            {'evento': {'sito': 'presente', 'calendar': 'eliminato'}},
        )
    with patch.object(app_module, '_riconciliazione_admin_se_necessaria', return_value=None):
        csrf = _login_admin(client)

    with patch.object(app_module, 'invia_email_conferma') as email:
        risposta = client.post(
            f'/admin/calendar/forza/Appuntamento/{appuntamento_id}',
            data={'_csrf_token': csrf},
        )

    assert risposta.status_code == 302
    email.assert_not_called()
    mock_servizio.events.return_value.insert.assert_called_once()
    mock_servizio.events.return_value.patch.assert_not_called()
    with flask_app.app_context():
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        anomalia = RegistroEvento.query.filter_by(
            categoria='riconciliazione_calendar',
            entita_id=appuntamento_id,
        ).one()
        assert appuntamento.google_event_id == 'evento-ripristinato'
        assert appuntamento.sincronizzazione == 'sincronizzato'
        assert appuntamento.stato == 'Confermato'
        assert anomalia.risolto_il is not None


def test_accetta_orario_calendar_aggiorna_db_audit_e_invia_spostamento(
    client,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.get.return_value.execute.return_value = {
        'id': 'evento-spostato',
        'status': 'confirmed',
        'summary': 'Test Spostamento Lavaggio auricolare',
        'start': {'dateTime': '2099-09-01T11:00:00+02:00'},
        'end': {'dateTime': '2099-09-01T11:45:00+02:00'},
    }
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Test Spostamento', telefono='3331234567', email='test@example.com',
            servizio='Lavaggio auricolare', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', sincronizzazione='difforme',
            google_event_id='evento-spostato',
            difformita_calendario=json.dumps({
                'inizio': {'sito': '2099-09-01T10:00+02:00', 'calendar': '2099-09-01T11:00+02:00'},
                'fine': {'sito': '2099-09-01T10:30+02:00', 'calendar': '2099-09-01T11:45+02:00'},
            }),
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
        app_module._registra_anomalia_sync(
            'Appuntamento', appuntamento_id,
            'Evento Calendar modificato esternamente: serve conferma.',
            json.loads(appuntamento.difformita_calendario),
        )
    with patch.object(app_module, '_riconciliazione_admin_se_necessaria', return_value=None):
        csrf = _login_admin(client)

    with patch.object(app_module, 'invia_email_spostamento', return_value=True) as email:
        risposta = client.post(
            f'/admin/calendar/accetta/Appuntamento/{appuntamento_id}',
            data={'_csrf_token': csrf},
        )

    assert risposta.status_code == 302
    email.assert_called_once()
    mock_servizio.events.return_value.patch.assert_called_once()
    with flask_app.app_context():
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        audit = app_module.RegistroModifica.query.filter_by(
            azione='accettazione_modifica_calendar',
            entita_tipo='Appuntamento',
            entita_id=appuntamento_id,
        ).one()
        assert appuntamento.data == '2099-09-01'
        assert appuntamento.ora == '11:00'
        assert appuntamento.duration_minutes == 45
        assert appuntamento.sincronizzazione == 'sincronizzato'
        assert '11:00' in audit.dettagli


def test_annullamento_da_evento_eliminato_usa_workflow_e_chiude_conflitto(client):
    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Test Annullamento', telefono='3331234567', email='test@example.com',
            servizio='Lavaggio auricolare', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato',
            sincronizzazione='eliminato_esternamente',
            google_event_id='evento-eliminato',
            difformita_calendario=json.dumps({
                'evento': {'sito': 'presente', 'calendar': 'eliminato'}
            }),
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
        app_module._registra_anomalia_sync(
            'Appuntamento', appuntamento_id,
            'Evento collegato eliminato da Google Calendar.',
            {'evento': {'sito': 'presente', 'calendar': 'eliminato'}},
        )
    csrf = _login_admin(client)

    with patch.object(app_module, 'invia_email_annullamento', return_value=True) as email, patch.object(
        app_module, 'elimina_evento_calendario', return_value=True
    ) as elimina:
        risposta = client.post(
            f'/admin/calendar/annulla/Appuntamento/{appuntamento_id}',
            data={'_csrf_token': csrf},
        )

    assert risposta.status_code == 302
    email.assert_called_once()
    elimina.assert_called_once()
    with flask_app.app_context():
        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        anomalia = RegistroEvento.query.filter_by(
            categoria='riconciliazione_calendar',
            entita_id=appuntamento_id,
        ).one()
        assert appuntamento.stato == 'Annullato'
        assert appuntamento.sincronizzazione == 'non_collegato'
        assert appuntamento.difformita_calendario is None
        assert anomalia.risolto_il is not None
        assert app_module.RegistroModifica.query.filter_by(
            azione='annullamento_da_conflitto_calendar',
            entita_id=appuntamento_id,
        ).count() == 1


def test_riconciliazione_si_ferma_al_primo_errore_calendar(
    app,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto
    with flask_app.app_context():
        for indice in range(2):
            db.session.add(Appuntamento(
                nome=f'Persona {indice}',
                telefono='3331234567',
                email=f'persona{indice}@example.com',
                servizio='Medicazione semplice',
                data='2099-09-01',
                ora=f'1{indice}:00',
                duration_minutes=30,
                stato='Confermato',
                google_event_id=f'evento-{indice}',
            ))
        db.session.commit()
    mock_servizio.events.return_value.get.return_value.execute.side_effect = TimeoutError(
        'Calendar non risponde'
    )

    with flask_app.app_context():
        risultato = app_module.riconcilia_calendario()
        eventi = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
        ).all()

    assert risultato['errore'] == 'Errore Calendar: TimeoutError'
    assert mock_servizio.events.return_value.get.call_count == 1
    assert len(eventi) == 1


def test_riallineamento_automatico_crea_evento_mancante_e_notifica_successo(
    app,
    google_calendar_scrittura_finto,
    monkeypatch,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.return_value = {
        'id': 'evento-riallineato',
    }
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'studio@example.com')
    monkeypatch.setitem(app.config, 'PUBLIC_BASE_URL', 'https://scstudioinfermieristico.it')

    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi', telefono='3331234567', email='mario@example.com',
            servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', sincronizzazione='errore',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id
        app_module.registra_evento(
            'google_calendar', 'errore', 'Scrittura Calendar fallita.',
            'Appuntamento', appuntamento_id,
        )

        with patch.object(
            app_module,
            '_invia_email_tracciata',
            return_value=True,
        ) as invia_email:
            risultato = app_module.riallinea_calendar_automaticamente()
            messaggio = invia_email.call_args.args[0]

        appuntamento = db.session.get(Appuntamento, appuntamento_id)
        errore_precedente = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
            entita_tipo='Appuntamento',
            entita_id=appuntamento_id,
        ).one()

    assert risultato['tentati'] == 1
    assert risultato['riusciti'] == 1
    assert risultato['falliti'] == 0
    assert appuntamento.google_event_id == 'evento-riallineato'
    assert appuntamento.sincronizzazione == 'sincronizzato'
    assert errore_precedente.risolto_il is not None
    assert 'Riallineamento Calendar riuscito' in messaggio.subject
    assert 'Appuntamento #' in messaggio.body
    assert 'https://scstudioinfermieristico.it/admin#admin-errori' in messaggio.body


def test_riallineamento_automatico_notifica_fallimento_senza_perdere_dato(
    app,
    google_calendar_scrittura_finto,
    monkeypatch,
):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.side_effect = TimeoutError(
        'Calendar non raggiungibile'
    )
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'studio@example.com')

    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi', telefono='3331234567', email='mario@example.com',
            servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', sincronizzazione='errore',
        )
        db.session.add(appuntamento)
        db.session.commit()
        appuntamento_id = appuntamento.id

        with patch.object(
            app_module,
            '_invia_email_tracciata',
            return_value=True,
        ) as invia_email:
            risultato = app_module.riallinea_calendar_automaticamente()
            messaggio = invia_email.call_args.args[0]

        appuntamento = db.session.get(Appuntamento, appuntamento_id)

    assert risultato['tentati'] == 1
    assert risultato['riusciti'] == 0
    assert risultato['falliti'] == 1
    assert appuntamento.google_event_id is None
    assert appuntamento.sincronizzazione == 'errore'
    assert 'Riallineamento Calendar fallito' in messaggio.subject
    assert 'Falliti: 1' in messaggio.body


def test_riallineamento_recupera_evento_creato_prima_di_un_timeout_senza_duplicarlo(
    app,
    google_calendar_scrittura_finto,
):
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appuntamento = Appuntamento(
            nome='Mario Rossi', telefono='3331234567', email='mario@example.com',
            servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
            duration_minutes=30, stato='Confermato', sincronizzazione='errore',
        )
        db.session.add(appuntamento)
        db.session.commit()
        mock_servizio.events.return_value.list.return_value.execute.return_value = {
            'items': [{
                'id': 'evento-gia-creato',
                'extendedProperties': {'private': {
                    'studioEntity': 'Appuntamento',
                    'studioEntityId': str(appuntamento.id),
                }},
            }],
        }

        with patch.object(
            app_module,
            'invia_email_esito_riallineamento_calendar',
            return_value=True,
        ):
            risultato = app_module.riallinea_calendar_automaticamente()

        appuntamento_id_calendar = appuntamento.google_event_id

    assert risultato['riusciti'] == 1
    assert appuntamento_id_calendar == 'evento-gia-creato'
    mock_servizio.events.return_value.insert.assert_not_called()
    mock_servizio.events.return_value.patch.assert_called_once()


def test_riallineamento_automatico_non_sovrascrive_anomalie_esterne_o_attese(app):
    with flask_app.app_context():
        db.session.add_all([
            Appuntamento(
                nome='Evento difforme', telefono='3331234567', email='uno@example.com',
                servizio='Medicazione semplice', data='2099-09-01', ora='10:00',
                duration_minutes=30, stato='Confermato', sincronizzazione='difforme',
                google_event_id='evento-difforme',
            ),
            Appuntamento(
                nome='Richiesta in attesa', telefono='3331234567', email='due@example.com',
                servizio='Medicazione semplice', data='2099-09-01', ora='11:00',
                duration_minutes=30, stato='In attesa', sincronizzazione='errore',
            ),
            Appuntamento(
                nome='Evento eliminato', telefono='3331234567', email='tre@example.com',
                servizio='Medicazione semplice', data='2099-09-01', ora='12:00',
                duration_minutes=30, stato='Confermato',
                sincronizzazione='eliminato_esternamente',
                google_event_id='evento-eliminato',
            ),
        ])
        db.session.commit()

        with patch.object(app_module, '_sincronizza_entita_calendar') as sincronizza, patch.object(
            app_module,
            'invia_email_esito_riallineamento_calendar',
        ) as notifica:
            risultato = app_module.riallinea_calendar_automaticamente()

    assert risultato['tentati'] == 0
    sincronizza.assert_not_called()
    notifica.assert_not_called()


def test_spostamento_rifiuta_slot_gia_occupato(client, google_calendar_scrittura_finto):
    """Spostare un appuntamento su uno slot già preso non deve sovrascrivere l'agenda."""
    mock_servizio = google_calendar_scrittura_finto

    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00',
                             stato='Confermato')
        occupato = Appuntamento(nome='Luisa Verdi', telefono='334', email='l@example.com',
                                servizio='Test', data='2026-09-02', ora='11:00',
                                stato='Confermato')
        db.session.add_all([appt, occupato])
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    resp = client.post(f'/admin/modifica/{appt_id}', data={
        'data': '2026-09-02', 'ora': '11:00',
        'duration_minutes': '30', '_csrf_token': csrf
    })

    assert 'non è più disponibile' in resp.text
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.data == '2026-09-01'
        assert aggiornato.ora == '10:00'


def test_nessuna_chiamata_google_se_non_configurato(client):
    """Se la scrittura su Google Calendar non è configurata, confermare un
    appuntamento deve funzionare normalmente senza errori né chiamate API."""
    with flask_app.app_context():
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Test', data='2026-09-01', ora='10:00')
        db.session.add(appt)
        db.session.commit()
        appt_id = appt.id

    csrf = _login_admin(client)
    resp = client.post(
        f'/admin/aggiorna/{appt_id}/Confermato',
        data={'_csrf_token': csrf, 'duration_minutes': '30'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.stato == 'Confermato'
        assert aggiornato.google_event_id is None


def test_google_analytics_non_presente_se_non_configurato(client):
    flask_app.config['GOOGLE_ANALYTICS_ID'] = None

    resp = client.get('/')

    assert 'google-analytics-id' not in resp.text
    assert 'analytics-consent.js' not in resp.text
    assert 'Preferenze cookie' not in resp.text


def test_google_analytics_presente_se_configurato(client):
    flask_app.config['GOOGLE_ANALYTICS_ID'] = 'G-TEST1234'

    try:
        resp = client.get('/')
    finally:
        flask_app.config['GOOGLE_ANALYTICS_ID'] = None

    assert 'meta name="google-analytics-id" content="G-TEST1234"' in resp.text
    assert 'analytics-consent.js' in resp.text
    assert 'Preferenze cookie' in resp.text


def test_canonical_e_open_graph_usano_origine_pubblica_configurata(client):
    flask_app.config['PUBLIC_BASE_URL'] = 'https://scstudioinfermieristico.it'
    try:
        resp = client.get('/consulenze-online', base_url='https://servizio.onrender.com')
    finally:
        flask_app.config['PUBLIC_BASE_URL'] = None

    assert '<link rel="canonical" href="https://scstudioinfermieristico.it/consulenze-online">' in resp.text
    assert '<meta property="og:url" content="https://scstudioinfermieristico.it/consulenze-online">' in resp.text
    assert 'https://servizio.onrender.com' not in resp.text


def test_homepage_ha_gerarchia_commerciale_e_seo(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert 'Non servono risposte perfette. Serve capire cosa osservare e cosa fare.' in resp.text
    assert 'Sapere cosa fare nei momenti che contano.' in resp.text
    assert 'In studio a Montesilvano oppure online.' in resp.text
    assert 'In studio oppure online, in tutta Italia.' not in resp.text
    assert 'data-conversion="home_hero_corsi"' in resp.text
    assert 'data-conversion="home_hero_call_sonno"' in resp.text
    assert resp.text.count('Scegli l’orario della call') == 2
    assert '<meta name="description"' in resp.text
    assert '<link rel="canonical"' in resp.text
    assert '<meta property="og:title"' in resp.text
    assert '"@type": "MedicalBusiness"' in resp.text
    assert 'class="btn-prenota"' not in resp.text
    assert '<behold-widget feed-id="kyzqTRnF2F6aeX6HaeUS"></behold-widget>' in resp.text
    assert 'behold-widget.js' in resp.text
    assert resp.text.index('class="home-instagram"') < resp.text.index('class="home-final-cta"')
    assert resp.text.index('class="home-final-cta"') < resp.text.index('class="home-clinical-band"')
    assert 'class="home-final-choice home-final-choice--courses"' in resp.text
    assert 'class="home-final-choice home-final-choice--sleep"' in resp.text
    assert 'class="home-final-detail"' in resp.text
    assert 'Scegli il prossimo passo, in base a ciò che ti serve adesso.' in resp.text
    assert 'home-birth-shell' in resp.text
    assert 'class="home-team-signature"' in resp.text
    assert 'Cinque professionisti nello stesso percorso' in resp.text
    assert 'class="home-method-sequence"' in resp.text
    assert resp.text.count('class="home-testimonial-featured"') == 1
    assert 'class="home-testimonial-featured"' in resp.text


def test_homepage_senza_date_mostra_un_ricontatto_compatto(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert 'data-home-scene="date"' not in resp.text
    assert 'data-home-scene-link="date"' not in resp.text
    assert 'Nuove date in preparazione.' in resp.text
    assert 'data-conversion="home_date_interesse"' in resp.text
    assert 'href="/iscrizione-corsi/interesse"' in resp.text
    assert 'id="cal-griglia"' not in resp.text
    assert 'id="corsi-data"' not in resp.text
    assert resp.text.count('data-home-scene=') == 7


def test_homepage_con_date_mostra_il_calendario_accessibile(client):
    _crea_data_corso('disostruzione-pediatrica', data='2099-07-16')

    resp = client.get('/')

    assert resp.status_code == 200
    assert 'data-home-scene="date"' in resp.text
    assert 'data-home-scene-link="date"' in resp.text
    assert 'id="cal-griglia"' in resp.text
    assert 'id="cal-dettaglio" role="status" aria-live="polite"' in resp.text
    assert 'id="corsi-data"' in resp.text
    assert resp.text.count('data-home-scene=') == 8


def test_homepage_ignora_le_date_passate_nella_regia(client):
    _crea_data_corso('disostruzione-pediatrica', data='2020-01-10')

    resp = client.get('/')

    assert resp.status_code == 200
    assert 'data-home-scene="date"' not in resp.text
    assert 'data-home-scene-link="date"' not in resp.text
    assert 'data-conversion="home_date_interesse"' in resp.text


def test_calendario_homepage_usa_controlli_accessibili():
    script = (Path(app_module.__file__).resolve().parent / 'static' / 'js' / 'calendario.js').read_text()

    assert "document.createElement('button')" in script
    assert "pulsante.type = 'button'" in script
    assert "pulsante.setAttribute('aria-expanded', 'false')" in script
    assert "Mostra i dettagli" in script
    assert "'Orario: '" in script
    assert "'Luogo: '" in script
    assert "chiudiDettaglio.addEventListener('click'" in script
    assert "nascondiDettaglio(true)" in script
    assert "pulsanteDaRipristinare.focus()" in script


def test_homepage_non_forza_il_layout_del_widget_instagram():
    stylesheet = (Path(app_module.__file__).resolve().parent / 'static' / 'css' / 'homepage.css').read_text()
    regola_widget = re.search(r'\.home-instagram-feed behold-widget\s*\{([^}]*)\}', stylesheet)
    regole_contenitore = re.findall(r'\.home-instagram-feed\s*\{([^}]*)\}', stylesheet)

    assert regola_widget is not None
    assert 'transform:' not in regola_widget.group(1)
    assert 'width:' not in regola_widget.group(1)
    assert 'height:' not in regola_widget.group(1)
    assert regole_contenitore
    altezze_massime = re.findall(r'max-height:\s*([^;]+)', '\n'.join(regole_contenitore))
    assert all(altezza.strip() == 'none' for altezza in altezze_massime)
    assert all('overflow: hidden' not in regola for regola in regole_contenitore)


def _csrf_richiesta_azienda(client):
    response = client.get('/aziende-e-gruppi')
    assert response.status_code == 200
    return re.search(r'name="_csrf_token" value="([^"]+)"', response.text).group(1)


def test_quiz_da_dove_parto_orienta_senza_raccogliere_dati(client):
    response = client.get('/da-dove-parto')

    assert response.status_code == 200
    assert response.text.count('<h1') == 1
    assert 'Da dove parto?' in response.text
    assert 'non vengono salvate né inviate' in response.text
    assert 'data-orientation-quiz' in response.text
    assert 'data-quiz-stage' in response.text
    assert response.text.count('orientation-panel') == 3
    assert 'js/da-dove-parto.js?v=1.1' in response.text
    assert '/aziende-e-gruppi' in response.text
    assert 'js/da-dove-parto.js' in response.text
    assert '<form' not in response.text


def test_richiesta_azienda_crea_coda_attivita_ed_email_tracciata(client):
    token = _csrf_richiesta_azienda(client)

    with patch.object(app_module.mail, 'send') as send_mock:
        response = client.post('/aziende-e-gruppi', data={
            '_csrf_token': token,
            'organizzazione': 'Scuola Test',
            'referente': 'Ada Referente',
            'telefono': '333 1234567',
            'email': 'ada@example.com',
            'tipo_organizzazione': 'Scuola o servizio educativo',
            'corso_tipo': 'disostruzione-pediatrica',
            'partecipanti_stimati': '24',
            'sede_preferita': 'Presso l’organizzazione',
            'periodo_preferito': 'Ottobre 2099',
            'note': 'Turni da concordare.',
            'consenso_privacy': 'on',
        })

    assert response.status_code == 302
    assert response.headers['Location'] == '/aziende-e-gruppi/conferma'
    assert send_mock.call_count >= 1
    with flask_app.app_context():
        richiesta = app_module.RichiestaAzienda.query.one()
        assert richiesta.organizzazione == 'Scuola Test'
        assert richiesta.stato == 'Nuova'
        assert richiesta.partecipanti_stimati == 24
        attivita = app_module.AttivitaAdmin.query.filter_by(
            entita_tipo='RichiestaAzienda',
            entita_id=richiesta.id,
            stato='Aperta',
        ).one()
        assert 'Qualificare richiesta' in attivita.titolo
        email = app_module.EmailOperativa.query.filter_by(
            entita_tipo='RichiestaAzienda',
            entita_id=richiesta.id,
        ).first()
        assert email is not None
        assert email.destinatario == 'ada@example.com'


def test_admin_vista_mensile_mostra_eventi_e_navigazione(client):
    with flask_app.app_context():
        db.session.add(Corso(
            titolo='Corso mensile test',
            tipo='bls-d',
            data='2099-08-18',
            ora='09:30',
            durata_ore=5,
            capienza_massima=14,
            stato='Aperto',
        ))
        db.session.add(Appuntamento(
            nome='Ada Calendario',
            telefono='3331234567',
            email='ada@example.com',
            servizio='Medicazione complessa',
            data='2099-08-19',
            ora='10:00',
            duration_minutes=45,
            note='Portare la documentazione della medicazione precedente.',
            stato='Confermato',
        ))
        db.session.add(app_module.BloccoAgenda(
            titolo='Chiusura studio',
            data='2099-08-20',
            ora='13:00',
            durata_minuti=180,
            note='Studio non disponibile.',
        ))
        db.session.commit()
    _login_admin(client)

    with patch.object(app_module, '_eventi_calendar_esterni', return_value=[]):
        response = client.get('/admin?vista=mese&mese=2099-08')

    assert response.status_code == 200
    assert 'agosto 2099' in response.text.lower()
    assert '<table class="admin-month">' in response.text
    assert response.text.count('class="admin-month-day') == 42
    assert response.text.count('<th scope="col">') == 7
    assert 'name="mese" value="2099-08"' in response.text
    assert 'data-submit-on-change' in response.text
    assert '>Mostra</button>' not in response.text
    assert 'Mese precedente' in response.text
    assert 'Mese successivo' in response.text
    assert '>Oggi</a>' in response.text
    assert response.text.index('Mese precedente') < response.text.index('id="admin-month-input"')
    assert response.text.index('id="admin-month-input"') < response.text.index('Mese successivo')
    assert response.text.index('Mese successivo') < response.text.index('>Oggi</a>')
    assert 'Corso mensile test' in response.text
    assert 'Chiusura studio' in response.text
    assert 'admin-month-event-appuntamento' in response.text
    assert 'admin-month-event-corso' in response.text
    assert 'admin-month-event-bloccoagenda' in response.text
    assert re.search(r'href="/admin/pratica/Corso/\d+#partecipanti-corso"[^>]*class="admin-month-event admin-month-event-corso"', response.text)
    assert 'Appuntamenti e call' in response.text
    assert 'Corsi' in response.text
    assert 'Pause e chiusure' in response.text
    assert 'data-calendar-preview' in response.text
    assert 'admin-month-preview-template' in response.text
    assert '<dt>Prestazione</dt><dd>Medicazione complessa</dd>' in response.text
    assert '<dt>Telefono</dt><dd>3331234567</dd>' in response.text
    assert 'Portare la documentazione della medicazione precedente.' in response.text
    assert '19/08/2099 · 10:00–10:45' in response.text
    assert '<dt>Sincronizzazione</dt>' in response.text
    assert 'Clicca sull’evento per aprire la scheda' in response.text
    assert 'vista=mese' in response.text
    assert 'data=2099-07-01' in response.text
    assert 'data=2099-09-01' in response.text
    assert '<details class="admin-surface"><summary>Nuovo appuntamento</summary>' in response.text
    assert '<details class="admin-surface"><summary>Aggiungi pausa o chiusura</summary>' in response.text


def test_admin_apre_la_vista_mensile_e_ordina_i_controlli(client):
    _login_admin(client)

    with patch.object(app_module, '_eventi_calendar_esterni', return_value=[]):
        response = client.get('/admin')
        response_vista_non_valida = client.get('/admin?vista=non-valida')

    assert response.status_code == 200
    assert '<table class="admin-month">' in response.text
    assert response_vista_non_valida.status_code == 200
    assert '<table class="admin-month">' in response_vista_non_valida.text
    indice_mese = response.text.index('>Mese</a>')
    indice_settimana = response.text.index('>Settimana</a>')
    indice_giorno = response.text.index('>Giorno</a>')
    assert indice_mese < indice_settimana < indice_giorno
    inizio_link_mese = response.text.rfind('<a', 0, indice_mese)
    assert 'filtro-btn attivo' in response.text[inizio_link_mese:indice_mese]


def test_admin_mostra_gli_strumenti_agenda_chiusi_in_ogni_vista(client):
    _login_admin(client)

    with patch.object(app_module, '_eventi_calendar_esterni', return_value=[]):
        for vista in ('mese', 'settimana', 'giorno'):
            response = client.get(f'/admin?vista={vista}')
            assert response.status_code == 200
            assert '<details class="admin-surface"><summary>Nuovo appuntamento</summary>' in response.text
            assert '<details class="admin-surface"><summary>Aggiungi pausa o chiusura</summary>' in response.text


def test_stato_azienda_sostituisce_automaticamente_la_prossima_attivita(client):
    with flask_app.app_context():
        richiesta = app_module.RichiestaAzienda(
            organizzazione='Azienda Test',
            referente='Mario Rossi',
            telefono='3331234567',
            email='mario@example.com',
            tipo_organizzazione='Azienda',
            corso_tipo='bls-d',
            sede_preferita='Da valutare insieme',
            consenso_privacy=True,
            scadenza_gestione=datetime(2099, 8, 1, 18, 0),
        )
        db.session.add(richiesta)
        db.session.flush()
        db.session.add(app_module.AttivitaAdmin(
            titolo='Qualificare richiesta · Azienda Test',
            scadenza=datetime(2099, 8, 1, 18, 0),
            entita_tipo='RichiestaAzienda',
            entita_id=richiesta.id,
        ))
        db.session.commit()
        richiesta_id = richiesta.id
    csrf = _login_admin(client)

    response = client.post(f'/admin/azienda/{richiesta_id}/stato', data={
        '_csrf_token': csrf,
        'stato': 'Qualificata',
        'scadenza': '2099-08-03T18:00',
    })

    assert response.status_code == 302
    dettaglio = client.get(response.headers['Location'])
    assert dettaglio.status_code == 200
    assert 'Invia la proposta' in dettaglio.text
    assert 'Crea il corso riservato' in dettaglio.text
    with flask_app.app_context():
        richiesta = db.session.get(app_module.RichiestaAzienda, richiesta_id)
        assert richiesta.stato == 'Qualificata'
        aperte = app_module.AttivitaAdmin.query.filter_by(
            entita_tipo='RichiestaAzienda',
            entita_id=richiesta_id,
            stato='Aperta',
        ).all()
        assert len(aperte) == 1
        assert aperte[0].titolo == 'Preparare proposta · Azienda Test'


def test_admin_converte_richiesta_azienda_in_corso_privato_non_pubblico(client):
    with flask_app.app_context():
        richiesta = app_module.RichiestaAzienda(
            organizzazione='Gruppo Riservato',
            referente='Lia Bianchi',
            telefono='3331234567',
            email='lia@example.com',
            tipo_organizzazione='Gruppo privato',
            corso_tipo='bls-d',
            partecipanti_stimati=20,
            sede_preferita='Presso l’organizzazione',
            consenso_privacy=True,
            stato='Qualificata',
        )
        db.session.add(richiesta)
        db.session.commit()
        richiesta_id = richiesta.id
    csrf = _login_admin(client)

    with patch.object(app_module, 'crea_o_aggiorna_evento_calendario_corso', return_value=True):
        response = client.post(f'/admin/azienda/{richiesta_id}/crea-corso', data={
            '_csrf_token': csrf,
            'tipo': 'bls-d',
            'titolo': 'BLSD · Gruppo Riservato',
            'data': '2099-09-12',
            'ora': '09:00',
            'durata_ore': '5',
            'capienza_massima': '20',
            'luogo': 'Sede aziendale',
        })

    assert response.status_code == 302
    with flask_app.app_context():
        richiesta = db.session.get(app_module.RichiestaAzienda, richiesta_id)
        assert richiesta.stato == 'Confermata'
        assert richiesta.corso_generato.stato == 'Chiuso'
        assert richiesta.corso_generato.capienza_massima == 20
    homepage = client.get('/')
    assert 'BLSD · Gruppo Riservato' not in homepage.text



def test_homepage_usa_staffetta_scontornata_e_profondita_solo_con_movimento_attivo():
    root = Path(app_module.__file__).resolve().parent
    script = (root / 'static' / 'js' / 'home-scroll-motion.js').read_text()
    stylesheet = (root / 'static' / 'css' / 'homepage.css').read_text()

    assert "{ from: 'hero-heart', fromScene: 0, to: 'courses-heart', toScene: 1 }" in script
    assert "{ from: 'courses-gallbladder', fromScene: 1, to: 'sleep-gallbladder', toScene: 2 }" in script
    assert "'hero-heart': 'url(\"#home-clip-heart-hero\")'" in script
    assert "'courses-heart': 'url(\"#home-clip-heart-courses\")'" in script
    assert 'clipPathUnits="objectBoundingBox"' in (root / 'templates' / 'homepage.html').read_text()
    assert 'element.style.clipPath = snapshot.clipPath' in script
    assert 'const progress = rawProgress' in script
    assert 'const visibility = Math.sin(Math.PI * progress)' in script
    assert 'const crossfade = smoothstep(0.3, 0.7, progress)' in script
    assert 'handoffSource.style.transform = `scale(${format(size / source.size)})`' in script
    assert 'handoffElement.style.height' not in script
    assert 'handoffElement.style.width' not in script
    assert 'will-change: opacity, transform' in stylesheet
    assert 'if (depthStates[index] === state) return' in script
    assert 'if (nextStyleKey === parallaxStyleKey) return' in script
    assert 'const renderDepth = () =>' in script
    assert "scene.style.setProperty('--home-focus-progress', focusProgress)" in script
    assert "window.matchMedia('(prefers-reduced-motion: reduce)')" in script
    assert "window.addEventListener('scroll', scheduleUpdate, { passive: true })" in script
    assert 'home-object-handoff:not(.is-visible)' in stylesheet
    assert 'drop-shadow(0 8px 9px var(--verde-scuro-a10))' in stylesheet
    assert 'home-depth-ready' in stylesheet
    assert 'const SNAP_TRAVEL_DURATION = 850' in script
    assert 'const easeInOutSine = (progress) =>' in script
    assert 'let handoffSnapshots = new Map()' in script
    assert 'const sceneChapters = Array.from' in script
    assert "chapter.classList.toggle('is-current', containsCurrentScene)" in script
    assert 'const measureAnchorSnapshot = (name) =>' in script
    assert 'const position = (sceneStops[index] - window.scrollY) / stageHeight' in script
    assert 'if (snapIsAnimating) return' in script
    assert 'window.scrollTo(0, startPosition + (distance * easeInOutSine(progress)));\n                update();' in script
    assert "window.addEventListener('wheel', onWheel, { passive: false })" in script
    assert "root.classList.add('home-snap-is-animating')" in script
    assert 'html.home-scroll-snap.home-snap-is-animating' in stylesheet
    assert 'snapStops = [...sceneStops]' in script
    assert 'snapStops.push' not in script
    assert 'const isLeavingFinalScene' in script
    assert "root.classList.add('home-footer-scroll')" in script
    assert 'const enterFooter = () =>' in script
    assert "root.classList.toggle('home-footer-visible', footerIsVisible)" in script
    assert 'html.home-scroll-snap.home-footer-scroll' in stylesheet
    assert '.home-scroll-story-ready.home-footer-visible .home-scene-nav' in stylesheet
    assert 'home-scene-nav-arrive' in stylesheet
    assert 'home-scene-nav-stitch' in stylesheet
    assert 'home-scene-nav-chapter' in stylesheet
    assert 'home-scene-nav-current' in stylesheet
    assert '.home-scene-nav__chapter:nth-child(3)' in stylesheet
    assert '.home-scroll-snap .page-homepage .site-footer' not in stylesheet


def test_homepage_mantiene_logo_rettangolare_e_filo_header_condivisi():
    stylesheet = (Path(app_module.__file__).resolve().parent / 'static' / 'css' / 'homepage.css').read_text()

    assert '.page-homepage .site-brand__mark' not in stylesheet
    assert '.page-homepage .site-nav__thread' not in stylesheet


def test_consulenza_online_e_verticale_sul_sonno(client):
    resp = client.get('/consulenze-online')

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert 'Consulenza del sonno infantile · online in tutta Italia' in resp.text
    assert '0-12' not in resp.text
    assert '0–12' not in resp.text
    assert 'Infermiera e consulente del sonno infantile' in resp.text
    assert 'La consulenza affronta anche il sonno sicuro e la SIDS?' in resp.text
    assert 'riduzione del rischio di SIDS' in resp.text
    assert 'https://www.salute.gov.it/new/it/tema/salute-del-bambino-e-delladolescente/sids/' in resp.text
    assert 'con attenzione a SIDS e sonno sicuro' in resp.text
    assert '127 ore' not in resp.text
    assert 'Master universitario' not in resp.text
    assert 'Consulenza mirata' in resp.text
    assert 'Percorso sonno personalizzato' in resp.text
    assert 'spannolinamento' not in resp.text.lower()
    assert 'ciuccio' not in resp.text.lower()
    assert 'data-conversion="sleep_hero_call"' in resp.text
    assert 'data-conversion="sleep_mid_call"' in resp.text
    assert 'data-conversion="sleep_mid_whatsapp"' not in resp.text
    assert 'data-conversion="sleep_final_call"' in resp.text
    assert resp.text.count('Scegli l’orario della call') >= 3
    assert 'Hai ancora un dubbio?' in resp.text
    assert 'Applicate un metodo rigido per farlo dormire?' in resp.text
    assert 'circa 20 minuti' in resp.text
    assert '15 minuti' not in resp.text
    assert resp.text.index('class="sleep-fit"') < resp.text.index('class="sleep-call-path"')
    assert resp.text.index('class="sleep-call-path"') < resp.text.index('class="sleep-together"')
    assert 'class="sleep-options"' not in resp.text
    assert 'class="sleep-expectations"' not in resp.text
    assert '"@type": "Service"' in resp.text


def test_pagina_prestazioni_usa_h1(client):
    resp = client.get('/prestazioni-infermieristiche')

    assert resp.status_code == 200
    assert '<h1>Prestazioni infermieristiche</h1>' in resp.text
    assert 'href="/prenota"' in resp.text
    assert 'Prenota una prestazione' in resp.text
    assert 'data-conversion="prestazioni_prenota"' in resp.text
    assert 'data-prestazioni-search' in resp.text
    assert 'data-prestazioni-catalog' in resp.text
    assert resp.text.count('data-service-group') == 4
    assert resp.text.count('data-service-row') == 31
    assert 'Lavaggio auricolare bilaterale' not in resp.text
    assert '20 € un orecchio' not in resp.text
    assert 'Terapie e somministrazioni' in resp.text
    assert 'Medicazioni' in resp.text
    assert 'Controlli e diagnostica' in resp.text
    assert 'Altre prestazioni' in resp.text
    assert 'Holter ECG 24 ore' in resp.text
    assert '80 €' in resp.text
    assert 'Le tariffe possono variare in base alla complessità della prestazione' in resp.text
    assert 'Gli interventi a domicilio non si prenotano direttamente online' in resp.text
    assert 'Per chiarire un dubbio puoi chiamare' in resp.text
    assert 'urgenze fuori orario' not in resp.text
    assert '<h2 id="studio-location-title">Dove ci troviamo</h2>' in resp.text
    assert "Via C. D'Agnese 43, 65015 Montesilvano (PE)" in resp.text
    assert 'Via Carmine' not in resp.text
    assert 'data-conversion="prestazioni_mappa"' in resp.text
    assert 'https://www.google.com/maps?q=' in resp.text
    assert 'loading="lazy"' in resp.text


def test_form_prenotazione_include_il_listino_aggiornato(client):
    resp = client.get('/prenota')

    assert resp.status_code == 200
    assert 'css/prestazioni.css' in resp.text
    assert 'data-service-picker' in resp.text
    assert resp.text.count('data-service-picker-group') == 4
    assert resp.text.count('data-service-category') == 4
    assert resp.text.count('data-service-option') == 31
    assert 'Terapie e somministrazioni' in resp.text
    assert 'Medicazioni' in resp.text
    assert 'Controlli e diagnostica' in resp.text
    assert 'Altre prestazioni' in resp.text
    assert '<input type="hidden" id="servizio" name="servizio"' in resp.text
    assert 'Passa sulla categoria per vedere le prestazioni.' in resp.text
    assert '<optgroup' not in resp.text
    assert 'data-service-name="Holter pressorio 24 ore"' in resp.text
    assert 'data-service-name="Medicazione chirurgica"' in resp.text
    assert 'data-service-name="Consulenza infermieristica"' in resp.text
    assert 'data-price="80 €"' in resp.text
    assert 'data-service-price-summary' in resp.text
    assert 'Tariffa in studio' in resp.text
    assert 'Ogni variazione viene comunicata prima della conferma.' in resp.text
    assert 'data-service-name="Assistenza domiciliare"' not in resp.text
    assert resp.text.index('name="consenso_privacy"') < resp.text.index('data-service-price-summary')
    assert resp.text.index('data-service-price-summary') < resp.text.index('id="btn-invia"')
    assert 'js/form-prenotazione.js?v=1.4' in resp.text


def test_form_prenotazione_ricentra_il_primo_campo_non_valido():
    script = Path('static/js/form-prenotazione.js').read_text()
    stylesheet = Path('static/css/prestazioni.css').read_text()

    assert "bookingForm.addEventListener('invalid'" in script
    assert "scrollIntoView({block: 'center'" in script
    assert "campoNonValido.focus({preventScroll: true})" in script
    assert 'scroll-margin-block: 7rem' in stylesheet


def test_email_appuntamento_include_indirizzo_e_link_admin(app, monkeypatch):
    monkeypatch.setitem(app.config, 'PUBLIC_BASE_URL', 'https://scstudioinfermieristico.it')
    appuntamento = Appuntamento(
        id=42,
        nome='Mario Rossi',
        telefono='3331234567',
        email='mario@example.com',
        servizio='Medicazione semplice',
        data='2099-09-01',
        ora='10:00',
        duration_minutes=30,
    )

    with app.test_request_context('/prenota'), patch.object(
        app_module,
        '_invia_email_tracciata',
        return_value=True,
    ) as invia_email:
        assert app_module.invia_email_conferma(appuntamento) is True
        messaggio_conferma = invia_email.call_args.args[0]

        assert app_module.invia_email_nuova_prenotazione(appuntamento) is True
        messaggio_ricezione = invia_email.call_args.args[0]

    assert "Via C. D'Agnese 43\n65015 Montesilvano (PE)" in messaggio_conferma.body
    assert 'https://scstudioinfermieristico.it/admin' in messaggio_ricezione.body


if __name__ == '__main__':
    pytest.main([__file__])
