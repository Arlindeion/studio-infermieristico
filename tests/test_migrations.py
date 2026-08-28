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
    'attivita_admin',
    'nota_admin',
    'email_operativa',
    'proposta_slot',
    'blocco_agenda',
    'registro_modifica',
    'collegamento_persona',
    'richiesta_azienda',
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


def _column_type(database_path, table_name, column_name):
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(f'PRAGMA table_info({table_name})').fetchall()
    return next(row[2] for row in rows if row[1] == column_name)


def _column_nullable(database_path, table_name, column_name):
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(f'PRAGMA table_info({table_name})').fetchall()
    return next(row[3] == 0 for row in rows if row[1] == column_name)


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
    appointment_columns = _column_names(database_path, 'appuntamento')
    assert 'duration_minutes' in appointment_columns
    assert 'scadenza_gestione' in appointment_columns
    assert 'sincronizzazione' in appointment_columns
    assert _column_type(database_path, 'iscrizione_corso', 'data_corso') == 'VARCHAR(255)'
    assert _column_nullable(database_path, 'persona_corso', 'telefono') is True

    _run_flask(env, 'db', 'upgrade')
    check = _run_flask(env, 'db', 'check')
    assert 'No new upgrade operations detected' in check.stdout + check.stderr


def test_upgrade_durata_appuntamento_preserva_righe_esistenti(tmp_path):
    database_path = tmp_path / 'pre_duration.sqlite'
    env = _migration_env(database_path)

    _run_flask(env, 'db', 'upgrade', '7f3c1a2d9e40')
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO appuntamento
                (nome, telefono, email, servizio, data, ora, stato)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'Persona Test',
                '0000000000',
                'test@example.invalid',
                'Prestazione test',
                '2099-01-01',
                '10:00',
                'In attesa',
            ),
        )
        connection.commit()

    _run_flask(env, 'db', 'upgrade')

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            'SELECT nome, duration_minutes FROM appuntamento'
        ).fetchone()
        revision = connection.execute(
            'SELECT version_num FROM alembic_version'
        ).fetchone()[0]

    assert row == ('Persona Test', 30)
    assert revision == 'f4c8a2d7e901'


def test_upgrade_estende_data_corso_e_preserva_righe_esistenti(tmp_path):
    database_path = tmp_path / 'pre_data_corso_length.sqlite'
    env = _migration_env(database_path)

    _run_flask(env, 'db', 'upgrade', 'd91e6b4f2a30')
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO iscrizione_corso
                (corso_tipo, corso_titolo, nome, telefono, codice_fiscale,
                 data_corso, tipo_richiesta, posti, consenso_privacy,
                 consenso_immagini, stato, posti_richiesti)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'disostruzione-pediatrica',
                'Disostruzione pediatrica',
                'Persona Test',
                '0000000000',
                'TSTPRS80A01G482X',
                '02/01/2027',
                'richiesta_iscrizione',
                1,
                1,
                0,
                'Nuova',
                1,
            ),
        )
        connection.commit()

    _run_flask(env, 'db', 'upgrade')

    etichetta = '02/01/2027 - ore 10:00 - S.C. Studio Infermieristico'
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'UPDATE iscrizione_corso SET data_corso = ? WHERE nome = ?',
            (etichetta, 'Persona Test'),
        )
        connection.commit()
        data_corso = connection.execute(
            'SELECT data_corso FROM iscrizione_corso WHERE nome = ?',
            ('Persona Test',),
        ).fetchone()[0]
        revision = connection.execute(
            'SELECT version_num FROM alembic_version'
        ).fetchone()[0]

    assert _column_type(database_path, 'iscrizione_corso', 'data_corso') == 'VARCHAR(255)'
    assert data_corso == etichetta
    assert revision == 'f4c8a2d7e901'


def test_upgrade_rende_opzionale_telefono_paziente_e_preserva_righe(tmp_path):
    database_path = tmp_path / 'pre_optional_patient_phone.sqlite'
    env = _migration_env(database_path)

    _run_flask(env, 'db', 'upgrade', 'e2f4a6b8c901')
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO persona_corso (nome, telefono, email)
            VALUES (?, ?, ?)
            """,
            ('Persona Test', '0000000000', 'test@example.invalid'),
        )
        connection.commit()

    _run_flask(env, 'db', 'upgrade')

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'UPDATE persona_corso SET telefono = NULL WHERE nome = ?',
            ('Persona Test',),
        )
        connection.commit()
        row = connection.execute(
            'SELECT nome, telefono, email FROM persona_corso'
        ).fetchone()
        revision = connection.execute(
            'SELECT version_num FROM alembic_version'
        ).fetchone()[0]

    assert _column_nullable(database_path, 'persona_corso', 'telefono') is True
    assert row == ('Persona Test', None, 'test@example.invalid')
    assert revision == 'f4c8a2d7e901'


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
    assert revision == 'f4c8a2d7e901'
