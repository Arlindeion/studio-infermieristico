import os
import base64
import re
import secrets
import subprocess
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime
from werkzeug.security import check_password_hash, generate_password_hash

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
    PercorsoAccompagnamento,
    IncontroAccompagnamento,
    PresenzaAccompagnamento,
    RegistroEvento,
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
        yield flask_app
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


def test_errore_404_usa_layout_pubblico_e_non_viene_indicizzato(client):
    resp = client.get('/pagina-inesistente')

    assert resp.status_code == 404
    assert resp.text.count('<h1') == 1
    assert 'Pagina non trovata' in resp.text
    assert '<meta name="robots" content="noindex,nofollow">' in resp.text
    assert 'Torna alla homepage' in resp.text


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


def test_health_check_e_esente_dai_limiti_globali(app):
    route_esenti = limiter.limit_manager._route_exemptions

    assert any(route.endswith('.healthz') for route in route_esenti)


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


def _csrf_call_sonno(client):
    response = client.get('/prenota-call-sonno')
    return re.search(r'name="_csrf_token" value="([^"]+)"', response.text).group(1)


def _dati_call_sonno(client, data=None, ora='09:00'):
    data = data or app_module.prima_data_call_disponibile().isoformat()
    return {
        'nome': 'Anna Verdi',
        'telefono': '333 1234567',
        'email': 'anna@example.com',
        'eta_bambino_mesi': '7',
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
    assert '320 €' in landing.text
    assert 'partono da <strong>75 €</strong>' in booking.text


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
        )
        db.session.add(call)
        db.session.commit()
        token = call.token_questionario

    response = client.get(f'/questionario-sonno/{token}')
    assert response.status_code == 200
    assert 'noindex,nofollow,noarchive' in response.text
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
    completed = client.post(f'/questionario-sonno/{token}', data=payload, follow_redirects=True)
    assert 'Questionario ricevuto' in completed.text
    with flask_app.app_context():
        assert QuestionarioSonno.query.count() == 1
        call_id = CallSonno.query.one().id

    protected = client.get(f'/admin/call-sonno/{call_id}/questionario')
    assert protected.status_code == 302
    _login_admin(client)
    admin_view = client.get(f'/admin/call-sonno/{call_id}/questionario')
    assert admin_view.status_code == 200
    assert 'Questionario sonno di Anna Verdi' in admin_view.text
    assert 'Ridurre i risvegli più lunghi' in admin_view.text

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
    assert 'css/tokens.css' in resp.text
    assert 'css/base.css' in resp.text
    assert 'css/components.css' in resp.text
    assert 'css/homepage.css' in resp.text
    assert 'js/home-scroll-motion.js' in resp.text
    assert 'css/consulenza.css' not in resp.text
    assert 'css/admin.css' not in resp.text
    assert 'css/stile.css' not in resp.text


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
    assert 'Vai al modulo' in resp.text
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
        'data_corso': data_corso_id,
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
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
        assert iscrizione.persona is not None
        assert iscrizione.persona.nome_bambino == 'Luca'
        assert iscrizione.persona.eta_bambino == '3 anni'
        assert iscrizione.extra_dict()['nome_bambino'] == 'Luca'
        assert '16/07/2099' in iscrizione.data_corso
        assert iscrizione.stato == 'Nuova'
        assert PersonaCorso.query.count() == 1


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
        assert iscrizione.persona.nome_bambino == 'Leo'
        assert iscrizione.persona.eta_bambino == '18 mesi'


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
        assert interesse.persona.codice_fiscale is None


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
        'codice_fiscale_secondo_partecipante': 'VRDLSU90A41G482Y',
        'scopo_informativo': 'on',
        'no_certificazione': 'on',
        'buono_stato_salute': 'on',
        'consenso_privacy': 'on',
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.posti == 2


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
        '_csrf_token': token,
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.filter_by(nome='Luisa Verdi').one()
        assert iscrizione.corso_id == int(data_corso_id)
        assert iscrizione.stato == 'Lista attesa'
        assert iscrizione.posti == 0
        assert iscrizione.posti_richiesti == 1


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
        '_csrf_token': token,
    })

    _login_admin(client)
    resp = client.get(f'/admin?corso_id={data_corso_id}')
    assert resp.status_code == 200
    assert 'Panoramica corsi e iscritti' in resp.text
    assert 'Disostruzione pediatrica' in resp.text
    assert 'posti stimati' in resp.text
    assert 'Richiesta iscrizione' in resp.text


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
    assert 'Visualizza iscritti per tipologia' in resp.text
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


# ─── Integrazione Google Calendar (Arzamed) ───

@pytest.fixture
def calendario_finto(app):
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
    app_module._servizio_calendario_cache = mock_servizio
    app_module._invalida_cache_calendario()
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._servizio_calendario_cache = None
    app_module._invalida_cache_calendario()
    app_module._cache_calendario['errore_registrato_il'] = 0


def test_errore_lettura_calendar_usa_cache_e_viene_registrato(app, monkeypatch):
    intervalli = [(
        datetime.fromisoformat('2099-08-11T10:00:00+02:00'),
        datetime.fromisoformat('2099-08-11T11:00:00+02:00'),
        'evento-cache',
    )]
    app_module._cache_calendario['per_data']['2099-08-11'] = {
        'intervalli': intervalli,
        'scaricato_il': 0,
    }
    app_module._cache_calendario['errore_registrato_il'] = 0
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(app.config, 'CALENDARIO_CACHE_SECONDI', 300)
    mock_servizio = MagicMock()
    mock_servizio.events.return_value.list.return_value.execute.side_effect = RuntimeError('rete assente')
    monkeypatch.setattr(app_module, '_servizio_calendario_cache', mock_servizio)

    with app.app_context():
        risultato = app_module._scarica_intervalli_calendario('2099-08-11')
        eventi = RegistroEvento.query.filter_by(
            categoria='google_calendar',
            esito='errore',
        ).all()

    assert risultato == intervalli
    assert len(eventi) == 1
    assert 'Lettura del calendario non disponibile' in eventi[0].messaggio
    app_module._servizio_calendario_cache = None
    app_module._invalida_cache_calendario()
    app_module._cache_calendario['errore_registrato_il'] = 0


def test_staging_senza_opt_in_non_contatta_calendar(app, monkeypatch):
    monkeypatch.setitem(app.config, 'APP_ENV', 'staging')
    monkeypatch.setitem(app.config, 'STAGING_LIVE_INTEGRATIONS', False)
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')
    monkeypatch.setitem(
        app.config,
        'GOOGLE_SERVICE_ACCOUNT_FILE',
        '/etc/secrets/google-calendar-service-account.json',
    )
    servizio_in_cache = MagicMock()
    app_module._servizio_calendario_cache = servizio_in_cache
    app_module._invalida_cache_calendario()

    with patch.object(
        app_module.service_account.Credentials,
        'from_service_account_file',
    ) as crea_credenziali, app.app_context():
        risultato = app_module._scarica_intervalli_calendario('2099-08-11')
        servizio = app_module._ottieni_servizio_calendario()
        eventi = RegistroEvento.query.filter_by(categoria='google_calendar').all()

    assert risultato == []
    assert servizio is None
    assert eventi == []
    servizio_in_cache.events.assert_not_called()
    crea_credenziali.assert_not_called()
    app_module._servizio_calendario_cache = None
    app_module._invalida_cache_calendario()


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
    monkeypatch.setattr(app_module, '_servizio_calendario_cache', mock_servizio)
    app_module._invalida_cache_calendario()

    intervalli = app_module._scarica_intervalli_calendario('2026-08-18')

    assert len(intervalli) == 2
    assert mock_servizio.events.return_value.list.call_count == 2
    seconda_chiamata = mock_servizio.events.return_value.list.call_args_list[1]
    assert seconda_chiamata.kwargs['pageToken'] == 'pagina-2'
    assert seconda_chiamata.kwargs['singleEvents'] is True
    app_module._servizio_calendario_cache = None
    app_module._invalida_cache_calendario()


def test_google_calendar_usa_scope_limitato_agli_eventi(app, monkeypatch):
    credenziali = object()
    client = MagicMock()
    monkeypatch.setitem(
        app.config,
        'GOOGLE_SERVICE_ACCOUNT_FILE',
        '/percorso/finto/google-calendar-service-account.json',
    )
    monkeypatch.setattr(app_module, '_servizio_calendario_cache', None)

    with patch.object(
        app_module.service_account.Credentials,
        'from_service_account_file',
        return_value=credenziali,
    ) as crea_credenziali, patch.object(
        app_module,
        'build',
        return_value=client,
    ):
        risultato = app_module._ottieni_servizio_calendario()

    assert risultato is client
    assert crea_credenziali.call_args.kwargs['scopes'] == [
        'https://www.googleapis.com/auth/calendar.events',
    ]
    app_module._servizio_calendario_cache = None


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


def test_modulo_privato_accompagnamento_conferma_iscrizione_e_presenze(client):
    slug, percorso_id = _crea_percorso_accompagnamento()
    resp = client.get(f'/iscrizione-accompagnamento/{slug}')
    assert resp.status_code == 200
    assert 'infermiera, ostetrica, psicologa, osteopata e nutrizionista' in resp.text
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
            'consenso_immagini': 'ACCONSENTO',
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    assert resp.headers['Location'] == '/iscrizione-accompagnamento/conferma'
    assert send_mock.call_count == 2
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        extra = iscrizione.extra_dict()
        assert iscrizione.percorso_accompagnamento_id == percorso_id
        assert iscrizione.stato == 'Confermato'
        assert iscrizione.tipo_richiesta == 'iscrizione_effettiva'
        assert iscrizione.posti == 1
        assert iscrizione.partecipazione == 'Coppia - partner si'
        assert extra['data_presunta_parto'] == '2100-01-10'
        assert extra['partner_presente'] == 'Si'
        assert iscrizione.consenso_immagini is True
        assert PersonaCorso.query.count() == 1
        assert PresenzaAccompagnamento.query.count() == 9


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
            '_csrf_token': token,
        })

    assert resp.status_code == 302
    with flask_app.app_context():
        iscrizione = IscrizioneCorso.query.one()
        assert iscrizione.stato == 'Confermato'
        assert PresenzaAccompagnamento.query.count() == 9
        eventi = RegistroEvento.query.filter_by(
            categoria='email',
            entita_tipo='IscrizioneCorso',
            entita_id=iscrizione.id,
        ).all()
        assert len(eventi) == 2
        assert all(evento.esito == 'errore' for evento in eventi)


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
def google_calendar_scrittura_finto(app):
    """Configura la scrittura su Google Calendar e sostituisce il client API
    reale con un mock, per verificare le chiamate senza contattare Google."""
    app_module.app.config['GOOGLE_CALENDAR_ID'] = 'finto@group.calendar.google.com'
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = '/percorso/finto/service-account.json'
    mock_servizio = MagicMock()
    mock_servizio.events.return_value.list.return_value.execute.return_value = {
        'items': [],
    }
    app_module._servizio_calendario_cache = mock_servizio
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._servizio_calendario_cache = None


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


def test_admin_conclude_call_e_invita_al_questionario_privato(client):
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
        'invia_email_questionario_sonno',
        return_value=True,
    ) as invio_questionario:
        resp = client.post(
            f'/admin/call-sonno/{call_id}/questionario',
            data={
                'formula_scelta': 'percorso',
                '_csrf_token': csrf,
            },
            follow_redirects=True,
        )

    assert resp.status_code == 200
    assert 'Questionario privato inviato.' in resp.text
    invio_questionario.assert_called_once()
    with flask_app.app_context():
        call = db.session.get(CallSonno, call_id)
        assert call.stato == 'Conclusa'
        assert call.formula_scelta == 'percorso'
        assert call.token_questionario
        assert call.questionario_inviato_il is not None
        token = call.token_questionario

    questionario = client.get(f'/questionario-sonno/{token}')
    assert questionario.status_code == 200
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in questionario.text


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
        appt = Appuntamento(nome='Mario Rossi', telefono='333', email='m@example.com',
                             servizio='Lavaggio auricolare', data='2026-09-01', ora='10:00')
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


def test_errore_calendar_non_perde_appuntamento_e_finisce_nel_registro(client, google_calendar_scrittura_finto):
    mock_servizio = google_calendar_scrittura_finto
    mock_servizio.events.return_value.insert.return_value.execute.side_effect = Exception('Calendar non disponibile')

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
        assert 'sincronizzazione Calendar' in evento.messaggio

    admin_resp = client.get('/admin')
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
    for etichetta in ['Agenda', 'Richieste', 'Corsi', 'Persone', 'Attività', 'Errori', 'Impostazioni']:
        assert f'<span>{etichetta}</span>' in resp.text
    assert 'Nuove richieste in attesa' in resp.text
    assert 'Riconciliazione automatica: ogni ora.' in resp.text


def test_admin_crea_appuntamento_in_attesa_con_scadenza(client):
    csrf = _login_admin(client)

    resp = client.post('/admin/appuntamento/aggiungi', data={
        '_csrf_token': csrf,
        'nome': 'Mario Rossi',
        'telefono': '3331234567',
        'email': 'mario@example.com',
        'servizio': 'Medicazione semplice',
        'data': '2099-09-01',
        'ora': '10:00',
        'duration_minutes': '45',
    })

    assert resp.status_code == 302
    with flask_app.app_context():
        appuntamento = Appuntamento.query.one()
        assert appuntamento.stato == 'In attesa'
        assert appuntamento.creato_da_admin is True
        assert appuntamento.duration_minutes == 45
        assert appuntamento.scadenza_gestione is not None


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
    assert 'Nei primi mesi non servono risposte perfette. Serve capire cosa osservare e cosa fare.' in resp.text
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


def test_homepage_non_forza_il_layout_del_widget_instagram():
    stylesheet = (Path(app_module.__file__).resolve().parent / 'static' / 'css' / 'homepage.css').read_text()
    regola_widget = re.search(r'\.home-instagram-feed behold-widget\s*\{([^}]*)\}', stylesheet)

    assert regola_widget is not None
    assert 'transform:' not in regola_widget.group(1)
    assert 'width:' not in regola_widget.group(1)
    assert 'height:' not in regola_widget.group(1)

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
    assert 'Consulenza del sonno infantile · 0-12 mesi' in resp.text
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


if __name__ == '__main__':
    pytest.main([__file__])
