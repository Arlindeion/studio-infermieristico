import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'appuntamenti.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or \
        ('S.C. Studio Infermieristico', MAIL_USERNAME)
    # Session settings
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    # CSRF
    WTF_CSRF_ENABLED = False  # we handle CSRF manually for now

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # In desarrollo, i cookie possono essere inviati anche su HTTP
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # In produzione, i cookie devono essere inviati solo su HTTPS
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    # Usa un database in memoria per i test
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Disabilita CSRF durante i test
    WTF_CSRF_ENABLED = False
    # Email non inviate realmente durante i test
    MAIL_SUPPRESS_SEND = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}