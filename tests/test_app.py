import os
import base64
import re
import secrets
import subprocess
import sys
from pathlib import Path
import pytest
import icalendar
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
    monkeypatch.setitem(app.config, 'MAIL_USERNAME', 'info@example.invalid')
    monkeypatch.setitem(app.config, 'MAIL_PASSWORD', 'password-email-test')
    monkeypatch.setitem(app.config, 'MAIL_DEFAULT_SENDER', 'Studio <info@example.invalid>')
    monkeypatch.setitem(app.config, 'MAIL_ADMIN_RECIPIENT', 'admin@example.invalid')
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ICS_URL', 'https://example.invalid/calendar.ics')
    monkeypatch.setitem(app.config, 'GOOGLE_SERVICE_ACCOUNT_FILE', str(service_account_file))
    monkeypatch.setitem(app.config, 'GOOGLE_CALENDAR_ID', 'calendar@example.invalid')

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
    while giorno.weekday() != 5:
        giorno += app_module.timedelta(days=1)

    assert app_module.orario_call_prenotabile(giorno.isoformat(), '09:00') is True


def test_prenotazione_call_sonno_salva_consenso_whatsapp_e_utm(client):
    dati = _dati_call_sonno(client)
    dati.update({
        'consenso_whatsapp': 'on',
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
        assert call.consenso_whatsapp is True
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


def test_promemoria_call_sonno_email_e_whatsapp_non_si_duplicano(app):
    adesso = datetime(2026, 9, 20, 10, 0, tzinfo=app_module.FUSO_ORARIO)
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True, consenso_whatsapp=True,
            data='2026-09-21', ora='09:00', stato='Confermata',
        )
        db.session.add(call)
        db.session.commit()

        with (
            patch.object(app_module, 'invia_email_promemoria_call_sonno', return_value=True) as email,
            patch.object(app_module, 'invia_whatsapp_promemoria_call_sonno', return_value=True) as whatsapp,
        ):
            app.config['WHATSAPP_REMINDERS_ENABLED'] = True
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)

        db.session.refresh(call)
        assert call.promemoria_email_24h_il is not None
        assert call.promemoria_whatsapp_24h_il is not None
        email.assert_called_once_with(call, 24)
        whatsapp.assert_called_once_with(call, 24)


def test_promemoria_whatsapp_non_parte_senza_consenso(app):
    adesso = datetime(2026, 9, 21, 7, 30, tzinfo=app_module.FUSO_ORARIO)
    with app.app_context():
        call = CallSonno(
            nome='Anna Verdi', telefono='3331234567', email='anna@example.com',
            eta_bambino_mesi=7, difficolta_principale='Risvegli notturni frequenti',
            consenso_privacy=True, consenso_whatsapp=False,
            data='2026-09-21', ora='09:00', stato='Confermata',
        )
        db.session.add(call)
        db.session.commit()

        with (
            patch.object(app_module, 'invia_email_promemoria_call_sonno', return_value=True),
            patch.object(app_module, 'invia_whatsapp_promemoria_call_sonno') as whatsapp,
        ):
            app.config['WHATSAPP_REMINDERS_ENABLED'] = True
            app_module.controlla_e_invia_promemoria_call_sonno(adesso)

        db.session.refresh(call)
        assert call.promemoria_email_2h_il is not None
        assert call.promemoria_whatsapp_2h_il is None
        whatsapp.assert_not_called()


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
    assert 'css/consulenza.css' not in resp.text
    assert 'css/admin.css' not in resp.text
    assert 'css/stile.css' not in resp.text


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
    assert 'Nuove esperienze da vivere anche a casa' in resp.text
    assert '6–18' in resp.text
    assert '18–36' in resp.text
    assert '3–5' in resp.text
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
    assert 'Farmacia Russo al fianco del percorso' in resp.text
    assert 'realizzato con la collaborazione della Farmacia Russo' in resp.text
    assert 'logo-farmacia-russo.png' in resp.text
    assert 'href="https://farmaciarussodomenico.it/"' in resp.text
    assert 'aria-label="Visita il sito della Farmacia Russo"' in resp.text
    assert resp.text.count('<h1>') == 1


def test_vecchio_url_prima_della_nascita_reindirizza_al_corso(client):
    resp = client.get('/prima-della-nascita')

    assert resp.status_code == 301
    assert resp.headers['Location'].endswith('/corso-accompagnamento-nascita')


def _crea_data_corso(corso_tipo, titolo='Corso test', data='2099-07-16', ora='18:00', luogo='Studio'):
    with flask_app.app_context():
        corso = Corso(
            titolo=titolo,
            tipo=corso_tipo,
            descrizione='Data aperta per test',
            data=data,
            ora=ora,
            luogo=luogo,
            durata_ore=2,
        )
        db.session.add(corso)
        db.session.commit()
        return str(corso.id)


def _crea_percorso_accompagnamento(slug='percorso-test', incontri=9):
    with flask_app.app_context():
        percorso = PercorsoAccompagnamento(
            titolo='Iscrizione al corso',
            slug=slug,
            descrizione='Edizione privata test',
            capienza_coppie=8,
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
    """Inietta un calendario Google finto (senza fare richieste di rete reali),
    con un appuntamento singolo e una chiusura settimanale ricorrente."""
    ics = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//IT
BEGIN:VEVENT
UID:appuntamento-arzamed-1@test
DTSTART;TZID=Europe/Rome:20260811T100000
DTEND;TZID=Europe/Rome:20260811T110000
SUMMARY:Visita paziente
END:VEVENT
BEGIN:VEVENT
UID:chiusura-ricorrente@test
DTSTART;TZID=Europe/Rome:20260803T150000
DTEND;TZID=Europe/Rome:20260803T160000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Chiuso
END:VEVENT
END:VCALENDAR
"""
    app_module.app.config['GOOGLE_CALENDAR_ICS_URL'] = 'https://esempio-fittizio.invalid/calendario.ics'
    app_module._cache_calendario['calendario'] = icalendar.Calendar.from_ical(ics)
    app_module._cache_calendario['scaricato_il'] = app_module.time.time()
    yield
    # Ripristina lo stato per non influenzare altri test
    app_module.app.config['GOOGLE_CALENDAR_ICS_URL'] = None
    app_module._cache_calendario['calendario'] = None
    app_module._cache_calendario['scaricato_il'] = 0


def test_calendario_google_blocca_appuntamento_singolo(calendario_finto):
    """Un appuntamento Arzamed (10:00-11:00) deve bloccare gli slot 10:00 e 10:30."""
    occupati = app_module.orari_occupati_da_calendario('2026-08-11')
    assert occupati == {'10:00', '10:30'}


def test_calendario_google_espande_ricorrenze(calendario_finto):
    """Una chiusura settimanale ricorrente deve applicarsi anche alle settimane successive."""
    occupati_originale = app_module.orari_occupati_da_calendario('2026-08-03')
    occupati_successivo = app_module.orari_occupati_da_calendario('2026-08-17')
    assert occupati_originale == {'15:00', '15:30'}
    assert occupati_successivo == {'15:00', '15:30'}


def test_calendario_google_nessun_evento(calendario_finto):
    """Un giorno senza eventi non deve risultare bloccato."""
    assert app_module.orari_occupati_da_calendario('2026-08-12') == set()


def test_endpoint_orari_occupati_unisce_db_e_calendario(client, calendario_finto):
    """L'endpoint /api/orari-occupati deve unire prenotazioni dal sito e impegni Arzamed."""
    with flask_app.app_context():
        appt = Appuntamento(
            nome='Prenotazione dal sito', telefono='333', email='sito@example.com',
            servizio='Test', data='2026-08-11', ora='16:00', stato='Confermato'
        )
        db.session.add(appt)
        db.session.commit()

    resp = client.get('/api/orari-occupati/2026-08-11')
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
        'servizio': 'Medicazione semplice', 'data': '2026-08-11', 'ora': '10:00',
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
    app_module._servizio_calendario_cache = mock_servizio
    yield mock_servizio
    app_module.app.config['GOOGLE_CALENDAR_ID'] = None
    app_module.app.config['GOOGLE_SERVICE_ACCOUNT_FILE'] = None
    app_module._servizio_calendario_cache = None


def test_tutte_le_prestazioni_bloccano_trenta_minuti():
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
    client.post(f'/admin/aggiorna/{appt_id}/Confermato', data={'_csrf_token': csrf})

    mock_servizio.events().insert.assert_called()
    corpo_inviato = mock_servizio.events().insert.call_args.kwargs['body']
    assert corpo_inviato['summary'] == 'Mario Rossi Lavaggio auricolare'

    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.google_event_id == 'evento-abc-123'


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
    client.post(f'/admin/aggiorna/{appt_id}/Confermato', data={'_csrf_token': csrf})

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
    assert 'Google Calendar non è stato aggiornato' in admin_resp.text


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
        'data': '2026-09-02', 'ora': '11:00', '_csrf_token': csrf
    })

    mock_servizio.events().patch.assert_called_once()
    kwargs = mock_servizio.events().patch.call_args.kwargs
    assert kwargs['eventId'] == 'evento-esistente'
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


def test_eliminazione_corso_elimina_evento_su_calendario(client, google_calendar_scrittura_finto):
    """Eliminare un corso in admin deve cancellare l'evento Google Calendar collegato."""
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
        assert db.session.get(Corso, corso_id) is None


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
        'data': domenica, 'ora': '10:00', '_csrf_token': csrf
    })

    assert 'studio è chiuso' in resp.text
    mock_servizio.events().patch.assert_not_called()
    mock_servizio.events().insert.assert_not_called()
    with flask_app.app_context():
        aggiornato = db.session.get(Appuntamento, appt_id)
        assert aggiornato.data == '2026-09-01'
        assert aggiornato.ora == '10:00'


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
        'data': '2026-09-02', 'ora': '11:00', '_csrf_token': csrf
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
        data={'_csrf_token': csrf},
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


def test_homepage_ha_gerarchia_commerciale_e_seo(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert 'Nei primi mesi non servono risposte perfette. Serve capire cosa osservare e cosa fare.' in resp.text
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
    assert resp.text.index('class="home-instagram"') < resp.text.index('class="home-clinical-band"')
    assert resp.text.index('class="home-clinical-band"') < resp.text.index('class="home-final-cta"')
    assert 'class="home-birth-shell"' in resp.text
    assert 'class="home-professionals-label"' in resp.text
    assert 'class="home-testimonial-featured"' in resp.text


def test_homepage_senza_date_mostra_un_ricontatto_compatto(client):
    resp = client.get('/')

    assert resp.status_code == 200
    assert 'home-dates home-dates--empty' in resp.text
    assert 'Le prossime date stanno arrivando.' in resp.text
    assert 'data-conversion="home_date_interesse"' in resp.text
    assert 'id="cal-griglia"' not in resp.text


def test_homepage_con_date_mostra_il_calendario_accessibile(client):
    _crea_data_corso('disostruzione-pediatrica', data='2099-07-16')

    resp = client.get('/')

    assert resp.status_code == 200
    assert 'home-dates--empty' not in resp.text
    assert 'id="cal-griglia"' in resp.text
    assert 'id="cal-dettaglio" role="status" aria-live="polite"' in resp.text


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


def test_consulenza_online_e_verticale_sul_sonno(client):
    resp = client.get('/consulenze-online')

    assert resp.status_code == 200
    assert resp.text.count('<h1') == 1
    assert 'Consulenza del sonno infantile · 0-12 mesi' in resp.text
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
    assert 'Per ulteriori informazioni, durante gli orari dello studio' in resp.text
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
    assert '<option value="Holter pressorio 24 ore"' in resp.text
    assert '<option value="Medicazione chirurgica"' in resp.text
    assert '<option value="Consulenza infermieristica"' in resp.text
    assert '<option value="Assistenza domiciliare"' not in resp.text


if __name__ == '__main__':
    pytest.main([__file__])
