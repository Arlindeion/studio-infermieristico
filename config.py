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
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL')) or \
        'sqlite:///' + os.path.join(basedir, 'appuntamenti.db')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Impostazioni email
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or \
        ('S.C. Studio Infermieristico', MAIL_USERNAME)
    # Impostazioni sessione
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    # CSRF
    WTF_CSRF_ENABLED = False  # gestiamo CSRF manualmente per ora
    # Calendario Google (sincronizzato da Arzamed): indirizzo segreto in
    # formato iCal del calendario su cui Arzamed segna appuntamenti e
    # chiusure studio. Vedi Impostazioni calendario > Integra calendario
    # su Google Calendar. Se non impostato, il sito funziona comunque,
    # semplicemente non conoscerà gli impegni presi solo su Arzamed.
    GOOGLE_CALENDAR_ICS_URL = os.environ.get('GOOGLE_CALENDAR_ICS_URL')
    # Per quanti secondi tenere in cache il calendario scaricato, per non
    # interrogare Google Calendar ad ogni singola richiesta del sito.
    CALENDARIO_CACHE_SECONDI = int(os.environ.get('CALENDARIO_CACHE_SECONDI') or 300)
    # Scrittura su Google Calendar: quando un appuntamento viene confermato
    # dall'area admin, viene creato un evento su questo calendario tramite un
    # account di servizio (permesso di modifica, non solo lettura). Se non
    # configurato, il sito funziona comunque: semplicemente non crea eventi.
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID')
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID')
    # Collegamento della videochiamata, incluso nelle conferme delle call sonno
    # solo quando configurato. In alternativa Selene comunica la modalità.
    SONNO_CALL_URL = os.environ.get('SONNO_CALL_URL')

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
    GOOGLE_CALENDAR_ICS_URL = None
    GOOGLE_SERVICE_ACCOUNT_FILE = None
    GOOGLE_CALENDAR_ID = None
    GOOGLE_ANALYTICS_ID = None
    SONNO_CALL_URL = None

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
