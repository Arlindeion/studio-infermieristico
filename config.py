import os
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def normalize_database_url(database_url):
    """Normalizza gli URL PostgreSQL forniti dagli hosting moderni."""
    if not database_url:
        return None
    if database_url.startswith('postgres://'):
        return database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    if database_url.startswith('postgresql://'):
        return database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return database_url


class Config:
    """Configurazione di base."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SECRET_KEY_IS_EPHEMERAL = not bool(os.environ.get('SECRET_KEY'))
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL')) or \
        'sqlite:///' + os.path.join(basedir, 'appuntamenti.db')
    DATABASE_URL_IS_EXPLICIT = bool(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Impostazioni email
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_ADMIN_RECIPIENT = os.environ.get('MAIL_ADMIN_RECIPIENT')
    # Impostazioni sessione
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    # CSRF
    WTF_CSRF_ENABLED = False  # gestiamo CSRF manualmente per ora
    # Per quanti secondi tenere in cache gli eventi letti tramite Google
    # Calendar API, per non interrogare Google ad ogni richiesta del sito.
    CALENDARIO_CACHE_SECONDI = int(os.environ.get('CALENDARIO_CACHE_SECONDI') or 300)
    # In caso di errore, una copia già letta resta utilizzabile per un tempo
    # limitato e il circuito evita raffiche di richieste verso Google.
    CALENDARIO_CACHE_STALE_SECONDI = int(
        os.environ.get('CALENDARIO_CACHE_STALE_SECONDI') or 900
    )
    CALENDARIO_CACHE_ERRORE_SECONDI = int(
        os.environ.get('CALENDARIO_CACHE_ERRORE_SECONDI') or 30
    )
    GOOGLE_CALENDAR_TIMEOUT_SECONDI = int(
        os.environ.get('GOOGLE_CALENDAR_TIMEOUT_SECONDI') or 5
    )
    # L'ingresso nell'admin può anticipare la riconciliazione oraria, ma una
    # finestra breve evita una chiamata a Google a ogni caricamento pagina.
    CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI = int(
        os.environ.get('CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI') or 180
    )
    # Lettura e scrittura Google Calendar usano lo stesso account di servizio
    # condiviso sul calendario operativo sincronizzato con Arzamed.
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID')
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID')
    # Origine pubblica usata per canonical, Open Graph, dati strutturati e
    # collegamenti assoluti nelle email. In produzione deve essere esplicita,
    # così il sottodominio Render non può diventare accidentalmente canonico.
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL')
    # Collegamento della videochiamata, incluso nelle conferme delle call sonno
    # solo quando configurato. In alternativa Selene comunica la modalità.
    SONNO_CALL_URL = os.environ.get('SONNO_CALL_URL')
    # Collegamenti PayPal Business a prezzo fisso. Restano facoltativi finché
    # il checkout non viene attivato e non devono essere hardcoded nei template.
    PAYPAL_LINK_SONNO_MIRATA = os.environ.get('PAYPAL_LINK_SONNO_MIRATA')
    PAYPAL_LINK_SONNO_PERCORSO = os.environ.get('PAYPAL_LINK_SONNO_PERCORSO')
    PAYPAL_LINK_SONNO_AFFIANCAMENTO = os.environ.get('PAYPAL_LINK_SONNO_AFFIANCAMENTO')
    BONIFICO_INTESTATARIO = os.environ.get('BONIFICO_INTESTATARIO')
    BONIFICO_IBAN = os.environ.get('BONIFICO_IBAN')
    # Ambiente operativo distinto dalla configurazione Flask: development,
    # staging o production. Lo staging pubblico richiede autenticazione HTTP.
    APP_ENV = os.environ.get('APP_ENV') or 'development'
    # Opt-in separato per collaudare integrazioni reali in uno staging pagato,
    # che resta comunque protetto da Basic Auth e noindex.
    STAGING_LIVE_INTEGRATIONS = os.environ.get(
        'STAGING_LIVE_INTEGRATIONS', 'false'
    ).lower() in ['true', 'on', '1']
    STAGING_AUTH_USERNAME = os.environ.get('STAGING_AUTH_USERNAME')
    STAGING_AUTH_PASSWORD = os.environ.get('STAGING_AUTH_PASSWORD')
    # Usate soltanto per creare il primo amministratore su un database vuoto.
    # Dopo il bootstrap in produzione vanno rimosse dal gestore dei segreti.
    ADMIN_BOOTSTRAP_USERNAME = os.environ.get('ADMIN_BOOTSTRAP_USERNAME')
    ADMIN_BOOTSTRAP_PASSWORD = os.environ.get('ADMIN_BOOTSTRAP_PASSWORD')

class DevelopmentConfig(Config):
    """Configurazione di sviluppo."""
    DEBUG = True
    # In sviluppo, i cookie possono essere inviati anche su HTTP
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Configurazione di produzione."""
    DEBUG = False
    # In produzione, i cookie devono essere inviati solo su HTTPS
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'

class TestingConfig(Config):
    """Configurazione di test."""
    TESTING = True
    # Usa un database in memoria per i test
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Disabilita CSRF durante i test
    WTF_CSRF_ENABLED = False
    # Disabilita il rate limiting durante i test: altrimenti, siccome i
    # contatori di Flask-Limiter restano in memoria per tutta la durata del
    # processo pytest (non si resettano da un test all'altro), una suite con
    # più login/prenotazioni ravvicinate rischia di far scattare i limiti a
    # metà test, causando fallimenti intermittenti indipendenti dal codice.
    RATELIMIT_ENABLED = False
    # Email non inviate realmente durante i test
    MAIL_SUPPRESS_SEND = True
    # Durante i test non contattiamo mai Google Calendar
    GOOGLE_SERVICE_ACCOUNT_FILE = None
    GOOGLE_CALENDAR_ID = None
    GOOGLE_ANALYTICS_ID = None
    PUBLIC_BASE_URL = None
    SONNO_CALL_URL = None
    PAYPAL_LINK_SONNO_MIRATA = None
    PAYPAL_LINK_SONNO_PERCORSO = None
    PAYPAL_LINK_SONNO_AFFIANCAMENTO = None
    BONIFICO_INTESTATARIO = None
    BONIFICO_IBAN = None
    APP_ENV = 'testing'
    STAGING_LIVE_INTEGRATIONS = False
    STAGING_AUTH_USERNAME = None
    STAGING_AUTH_PASSWORD = None

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
