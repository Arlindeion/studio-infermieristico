import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    'admin',
    'alembic_version',
    'appuntamento',
    'call_sonno',
    'corso',
    'incontro_accompagnamento',
    'iscrizione_corso',
    'percorso_accompagnamento',
    'persona_corso',
    'presenza_accompagnamento',
    'questionario_sonno',
    'registro_evento',
}


def _migration_env(database_path):
    env = os.environ.copy()
    env.update({
        'FLASK_ENV': 'development',
        'APP_ENV': 'development',
        'DATABASE_URL': f'sqlite:///{database_path}',
        'SECRET_KEY': 'migration-test-only',
        'DISABLE_SCHEDULER': 'true',
    })
    return env


def _run_flask(env, *args):
    return subprocess.run(
        [sys.executable, '-m', 'flask', '--app', 'app', *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _table_names(database_path):
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def _column_names(database_path, table_name):
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(f'PRAGMA table_info({table_name})').fetchall()
    return {row[1] for row in rows}


def test_upgrade_crea_schema_vuoto_ed_e_idempotente(tmp_path):
    database_path = tmp_path / 'empty.sqlite'
    env = _migration_env(database_path)

    _run_flask(env, 'db', 'upgrade')
    assert EXPECTED_TABLES <= _table_names(database_path)
    call_columns = _column_names(database_path, 'call_sonno')
    assert 'promemoria_email_24h_il' in call_columns
    assert 'promemoria_email_2h_il' in call_columns
    assert 'consenso_whatsapp' not in call_columns
    assert 'promemoria_whatsapp_24h_il' not in call_columns
    assert 'promemoria_whatsapp_2h_il' not in call_columns

    _run_flask(env, 'db', 'upgrade')
    check = _run_flask(env, 'db', 'check')
    assert 'No new upgrade operations detected' in check.stdout + check.stderr


def test_baseline_adotta_schema_rappresentativo_senza_perdere_dati(tmp_path):
    database_path = tmp_path / 'representative.sqlite'
    env = _migration_env(database_path)
    setup_script = """
from app import app, db, Admin, Appuntamento
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    db.session.add(Admin(username='utente-test', password=generate_password_hash('password-test-lunga-2026')))
    db.session.add(Appuntamento(
        nome='Persona Test',
        telefono='0000000000',
        email='test@example.invalid',
        servizio='Prestazione test',
        data='2099-01-01',
        ora='10:00',
    ))
    db.session.commit()
"""
    subprocess.run(
        [sys.executable, '-c', setup_script],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    _run_flask(env, 'db', 'stamp', 'head')
    _run_flask(env, 'db', 'upgrade')
    _run_flask(env, 'db', 'check')

    with sqlite3.connect(database_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM admin').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM appuntamento').fetchone()[0] == 1
        revision = connection.execute(
            'SELECT version_num FROM alembic_version'
        ).fetchone()[0]
    assert revision == '7f3c1a2d9e40'
