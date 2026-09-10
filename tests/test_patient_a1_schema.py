import ast
import importlib.util
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / 'migrations' / 'versions'
A1_REVISION = '8f2c7d1e4a90'
A1_PARENT = 'c9e1f4a7b260'
A1_MIGRATION = MIGRATIONS_DIR / '8f2c7d1e4a90_schema_pazienti_v2_paz_a1.py'
NEW_TABLES = {
    'persona',
    'recapito_persona',
    'relazione_persona',
    'segnalazione_duplicato',
    'fusione_persona',
}


def _revision_metadata(path):
    tree = ast.parse(path.read_text())
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {'revision', 'down_revision'}:
                values[target.id] = ast.literal_eval(node.value)
    return values


def _migration_files():
    result = {}
    for path in MIGRATIONS_DIR.glob('*.py'):
        metadata = _revision_metadata(path)
        revision = metadata.get('revision')
        if revision:
            result[revision] = (path, metadata.get('down_revision'))
    return result


def _chain_to(revision):
    files = _migration_files()
    chain = []
    current = revision
    while current:
        path, parent = files[current]
        chain.append((current, path))
        current = parent
    return list(reversed(chain))


def _load_migration(revision, path):
    spec = importlib.util.spec_from_file_location(f'test_migration_{revision}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sqlite_engine():
    engine = sa.create_engine('sqlite:///:memory:')

    @event.listens_for(engine, 'connect')
    def _enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

    return engine


def _upgrade_to_a1(connection):
    context = MigrationContext.configure(connection)
    loaded = {}
    for revision, path in _chain_to(A1_REVISION):
        module = _load_migration(revision, path)
        loaded[revision] = module
        with Operations.context(context):
            module.upgrade()
    return context, loaded


def _insert_person(connection, name='Persona'):
    return connection.execute(
        sa.text("INSERT INTO persona (nome, stato) VALUES (:name, 'attiva')"),
        {'name': name},
    ).lastrowid


def _insert_admin(connection):
    return connection.execute(
        sa.text("INSERT INTO admin (username, password_hash) VALUES ('review-admin', 'x')")
    ).lastrowid


def test_a1_parent_matches_reviewed_snapshot_head():
    metadata = _revision_metadata(A1_MIGRATION)
    assert metadata['down_revision'] == A1_PARENT


def test_a1_upgrade_and_downgrade_preserve_populated_legacy_graph():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        for revision, path in _chain_to(A1_PARENT):
            module = _load_migration(revision, path)
            with Operations.context(context):
                module.upgrade()

        patient_id = connection.execute(
            sa.text("INSERT INTO persona_corso (nome, telefono, email) VALUES ('Legacy Test', '3331234567', 'legacy@example.invalid')")
        ).lastrowid
        appointment_id = connection.execute(
            sa.text("""
                INSERT INTO appuntamento (nome, telefono, email, servizio, data, ora, stato)
                VALUES ('Legacy Test', '3331234567', 'legacy@example.invalid', 'Test', '2099-01-01', '10:00', 'In attesa')
            """)
        ).lastrowid
        call_id = connection.execute(sa.text("""
            INSERT INTO call_sonno (
                nome, telefono, email, eta_bambino_mesi,
                difficolta_principale, consenso_privacy, data, ora,
                stato, creato_il, aggiornato_il, sincronizzazione
            ) VALUES (
                'Legacy Call', '3330000000', 'call@example.invalid', 6,
                'Test', 1, '2099-01-01', '09:00',
                'In attesa', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                'da_sincronizzare'
            )
        """)).lastrowid
        questionnaire_id = connection.execute(sa.text("""
            INSERT INTO questionario_sonno (
                call_sonno_id, risposte, consenso_dati_sanitari,
                consenso_marketing, compilato_il
            ) VALUES (:call_id, '{}', 1, 0, CURRENT_TIMESTAMP)
        """), {'call_id': call_id}).lastrowid
        registration_id = connection.execute(sa.text("""
            INSERT INTO iscrizione_corso (
                persona_id, corso_tipo, corso_titolo, nome, telefono,
                codice_fiscale, tipo_richiesta, posti, consenso_privacy,
                consenso_immagini, consenso_dati_gravidanza, stato,
                posti_richiesti
            ) VALUES (
                :person_id, 'BLSD', 'Test', 'Legacy Test', '3331234567',
                'RSSMRA80A01H501U', 'richiesta_iscrizione', 1, 1,
                0, 0, 'Nuova', 1
            )
        """), {'person_id': patient_id}).lastrowid
        authorization_id = connection.execute(sa.text("""
            INSERT INTO autorizzazione_immagini (
                iscrizione_id, soggetto_nome, soggetto_tipo,
                finalita_didattica, finalita_informativa,
                finalita_promozionale, canale_sito, canale_social,
                canale_materiali, responsabilita_esclusiva,
                versione_informativa, prestato_il
            ) VALUES (
                :registration_id, 'Legacy Test', 'adulto', 0, 0, 0,
                0, 0, 0, 0, 'test', CURRENT_TIMESTAMP
            )
        """), {'registration_id': registration_id}).lastrowid
        path_id = connection.execute(sa.text("""
            INSERT INTO percorso_accompagnamento (titolo, slug, stato)
            VALUES ('Legacy Path', 'legacy-path', 'Aperto')
        """)).lastrowid
        meeting_id = connection.execute(sa.text("""
            INSERT INTO incontro_accompagnamento (
                percorso_id, numero, data, professionista, tema
            ) VALUES (:path_id, 1, '2099-01-01', 'Test', 'Test')
        """), {'path_id': path_id}).lastrowid
        attendance_id = connection.execute(sa.text("""
            INSERT INTO presenza_accompagnamento (iscrizione_id, incontro_id)
            VALUES (:registration_id, :meeting_id)
        """), {
            'registration_id': registration_id,
            'meeting_id': meeting_id,
        }).lastrowid

        a1 = _load_migration(A1_REVISION, A1_MIGRATION)
        with Operations.context(context):
            a1.upgrade()

        inspector = sa.inspect(connection)
        assert NEW_TABLES <= set(inspector.get_table_names())
        assert 'persona_id' in {column['name'] for column in inspector.get_columns('appuntamento')}
        assert 'persona_id' in {column['name'] for column in inspector.get_columns('call_sonno')}
        assert {'persona_id', 'persona_v2_id'} <= {
            column['name'] for column in inspector.get_columns('iscrizione_corso')
        }
        assert connection.execute(
            sa.text('SELECT nome FROM persona_corso WHERE id = :id'), {'id': patient_id}
        ).scalar_one() == 'Legacy Test'
        assert connection.execute(
            sa.text('SELECT nome, persona_id FROM appuntamento WHERE id = :id'), {'id': appointment_id}
        ).one() == ('Legacy Test', None)
        assert connection.execute(
            sa.text('SELECT call_sonno_id FROM questionario_sonno WHERE id = :id'),
            {'id': questionnaire_id},
        ).scalar_one() == call_id
        assert connection.execute(
            sa.text('SELECT iscrizione_id FROM autorizzazione_immagini WHERE id = :id'),
            {'id': authorization_id},
        ).scalar_one() == registration_id
        assert connection.execute(
            sa.text('SELECT iscrizione_id FROM presenza_accompagnamento WHERE id = :id'),
            {'id': attendance_id},
        ).scalar_one() == registration_id
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []

        with Operations.context(context):
            a1.downgrade()

        assert connection.execute(
            sa.text('SELECT call_sonno_id FROM questionario_sonno WHERE id = :id'),
            {'id': questionnaire_id},
        ).scalar_one() == call_id
        assert connection.execute(
            sa.text('SELECT iscrizione_id FROM autorizzazione_immagini WHERE id = :id'),
            {'id': authorization_id},
        ).scalar_one() == registration_id
        assert connection.execute(
            sa.text('SELECT iscrizione_id FROM presenza_accompagnamento WHERE id = :id'),
            {'id': attendance_id},
        ).scalar_one() == registration_id
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []


def test_a1_sqlite_inline_practice_fks_match_expected_targets_and_actions():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        for table_name, column_name in {
            'appuntamento': 'persona_id',
            'call_sonno': 'persona_id',
            'iscrizione_corso': 'persona_v2_id',
        }.items():
            foreign_keys = connection.exec_driver_sql(
                f'PRAGMA foreign_key_list("{table_name}")'
            ).all()
            patient_foreign_key = next(
                row for row in foreign_keys if row[3] == column_name
            )
            assert patient_foreign_key[2] == 'persona'
            assert patient_foreign_key[4] == 'id'
            assert patient_foreign_key[6].upper() == 'RESTRICT'

        with pytest.raises(IntegrityError):
            connection.execute(sa.text("""
                INSERT INTO appuntamento (
                    nome, telefono, email, servizio, data, ora, stato, persona_id
                ) VALUES (
                    'FK Test', '3330000000', 'fk@example.invalid', 'Test',
                    '2099-01-01', '10:00', 'In attesa', 999999
                )
            """))


def test_persona_lifecycle_is_bidirectionally_coherent_and_anonymization_is_deferred():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        columns = {column['name'] for column in sa.inspect(connection).get_columns('persona')}
        assert 'dati_anonimizzati_il' not in columns

        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO persona (nome, stato, archiviato_il) "
                "VALUES ('Attiva incoerente', 'attiva', CURRENT_TIMESTAMP)"
            ))
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO persona (nome, stato) VALUES ('Archiviata incoerente', 'archiviata')"
            ))
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO persona (nome, stato) VALUES ('Anonima non supportata', 'anonimizzata')"
            ))
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO persona (nome, stato) VALUES ('Fusa non supportata in A1', 'fusa')"
            ))

        connection.execute(sa.text(
            "INSERT INTO persona (nome, stato, archiviato_il) "
            "VALUES ('Archiviata valida', 'archiviata', CURRENT_TIMESTAMP)"
        ))


def test_recapito_constraints_prevent_hard_edge_inconsistencies():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        person_id = _insert_person(connection)
        connection.execute(
            sa.text("""
                INSERT INTO recapito_persona
                    (persona_id, tipo, valore, valore_normalizzato, principale)
                VALUES (:person, 'telefono', '333 111 1111', '3331111111', 1)
            """),
            {'person': person_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO recapito_persona
                        (persona_id, tipo, valore, valore_normalizzato, principale)
                    VALUES (:person, 'telefono', '333 222 2222', '3332222222', 1)
                """),
                {'person': person_id},
            )


def test_archived_recapito_cannot_remain_primary():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        person_id = _insert_person(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO recapito_persona
                        (persona_id, tipo, valore, valore_normalizzato, principale, archiviato_il)
                    VALUES (:person, 'email', 'a@example.invalid', 'a@example.invalid', 1, CURRENT_TIMESTAMP)
                """),
                {'person': person_id},
            )


def test_relationship_constraints_block_self_and_multiple_primary_contacts():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        assisted_id = _insert_person(connection, 'Assistita')
        first_id = _insert_person(connection, 'Referente 1')
        second_id = _insert_person(connection, 'Referente 2')

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO relazione_persona
                        (persona_assistita_id, persona_referente_id, ruolo, stato)
                    VALUES (:person, :person, 'madre', 'attiva')
                """),
                {'person': assisted_id},
            )

        connection.execute(
            sa.text("""
                INSERT INTO relazione_persona
                    (persona_assistita_id, persona_referente_id, ruolo, contatto_principale, stato)
                VALUES (:assisted, :referent, 'madre', 1, 'attiva')
            """),
            {'assisted': assisted_id, 'referent': first_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO relazione_persona
                        (persona_assistita_id, persona_referente_id, ruolo, contatto_principale, stato)
                    VALUES (:assisted, :referent, 'padre', 1, 'attiva')
                """),
                {'assisted': assisted_id, 'referent': second_id},
            )


def test_multiple_consent_referents_are_allowed_but_not_used_by_a1_routes():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        assisted_id = _insert_person(connection, 'Assistita')
        first_id = _insert_person(connection, 'Referente 1')
        second_id = _insert_person(connection, 'Referente 2')
        for referent_id, role in [(first_id, 'madre'), (second_id, 'padre')]:
            connection.execute(
                sa.text("""
                    INSERT INTO relazione_persona
                        (persona_assistita_id, persona_referente_id, ruolo, referente_consensi, stato)
                    VALUES (:assisted, :referent, :role, 1, 'attiva')
                """),
                {'assisted': assisted_id, 'referent': referent_id, 'role': role},
            )
        assert connection.execute(
            sa.text('SELECT COUNT(*) FROM relazione_persona WHERE referente_consensi = 1')
        ).scalar_one() == 2


def test_duplicate_storage_is_minimal_and_has_no_decision_or_privacy_payload():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        columns = {column['name'] for column in sa.inspect(connection).get_columns('segnalazione_duplicato')}
        assert columns == {'id', 'persona_a_id', 'persona_b_id', 'livello', 'creato_il'}

        first_id = _insert_person(connection, 'A')
        second_id = _insert_person(connection, 'B')
        connection.execute(
            sa.text("""
                INSERT INTO segnalazione_duplicato (persona_a_id, persona_b_id, livello)
                VALUES (:a, :b, 'forte')
            """),
            {'a': first_id, 'b': second_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO segnalazione_duplicato (persona_a_id, persona_b_id, livello)
                    VALUES (:a, :b, 'probabile')
                """),
                {'a': first_id, 'b': second_id},
            )


def test_merge_storage_has_no_json_snapshot_and_requires_admin():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        columns = {column['name'] for column in sa.inspect(connection).get_columns('fusione_persona')}
        assert {'dettagli', 'snapshot_tecnico', 'mappa_valori', 'payload_version'}.isdisjoint(columns)

        first_id = _insert_person(connection, 'A')
        second_id = _insert_person(connection, 'B')
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO fusione_persona
                        (persona_principale_id, persona_secondaria_id, operazione_id, stato)
                    VALUES (:a, :b, '00000000-0000-0000-0000-000000000001', 'applicata')
                """),
                {'a': first_id, 'b': second_id},
            )


def test_legacy_mapping_is_fk_protected_and_restricts_delete():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("INSERT INTO persona (nome, stato, legacy_persona_corso_id) VALUES ('A', 'attiva', 999999)")
            )

        legacy_id = connection.execute(
            sa.text("INSERT INTO persona_corso (nome) VALUES ('Legacy protetta')")
        ).lastrowid
        connection.execute(
            sa.text("INSERT INTO persona (nome, stato, legacy_persona_corso_id) VALUES ('A', 'attiva', :legacy)"),
            {'legacy': legacy_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(sa.text('DELETE FROM persona_corso WHERE id = :legacy'), {'legacy': legacy_id})


def test_a1_downgrade_before_backfill_removes_only_a1_schema():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        context, loaded = _upgrade_to_a1(connection)
        with Operations.context(context):
            loaded[A1_REVISION].downgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert not (NEW_TABLES & tables)
        assert {'persona_corso', 'appuntamento', 'call_sonno', 'iscrizione_corso'} <= tables
        assert 'persona_id' not in {column['name'] for column in sa.inspect(connection).get_columns('appuntamento')}
        assert 'persona_v2_id' not in {column['name'] for column in sa.inspect(connection).get_columns('iscrizione_corso')}


def test_a1_offline_ddl_compiles_for_postgresql_but_is_not_real_postgres_evidence():
    import io

    buffer = io.StringIO()
    context = MigrationContext.configure(
        url='postgresql://',
        opts={'as_sql': True, 'output_buffer': buffer},
    )
    module = _load_migration(A1_REVISION, A1_MIGRATION)
    with Operations.context(context):
        module.upgrade()
    ddl = buffer.getvalue()
    assert 'CREATE TABLE persona' in ddl
    assert 'WHERE principale IS TRUE AND archiviato_il IS NULL' in ddl
    assert 'fk_appuntamento_persona_v2' in ddl


def test_a1_can_be_upgraded_again_after_pre_backfill_downgrade():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        context, loaded = _upgrade_to_a1(connection)
        with Operations.context(context):
            loaded[A1_REVISION].downgrade()
        with Operations.context(context):
            loaded[A1_REVISION].upgrade()
        assert NEW_TABLES <= set(sa.inspect(connection).get_table_names())


def test_only_one_active_communication_referent_is_allowed():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        assisted_id = _insert_person(connection, 'Assistita')
        first_id = _insert_person(connection, 'Referente 1')
        second_id = _insert_person(connection, 'Referente 2')
        connection.execute(
            sa.text("""
                INSERT INTO relazione_persona
                    (persona_assistita_id, persona_referente_id, ruolo, referente_comunicazioni, stato)
                VALUES (:assisted, :referent, 'madre', 1, 'attiva')
            """),
            {'assisted': assisted_id, 'referent': first_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO relazione_persona
                        (persona_assistita_id, persona_referente_id, ruolo, referente_comunicazioni, stato)
                    VALUES (:assisted, :referent, 'padre', 1, 'attiva')
                """),
                {'assisted': assisted_id, 'referent': second_id},
            )


def test_archived_relationship_cannot_keep_active_flags():
    engine = _sqlite_engine()
    with engine.begin() as connection:
        _upgrade_to_a1(connection)
        assisted_id = _insert_person(connection, 'Assistita')
        referent_id = _insert_person(connection, 'Referente')
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("""
                    INSERT INTO relazione_persona
                        (persona_assistita_id, persona_referente_id, ruolo, contatto_principale,
                         stato, archiviato_il)
                    VALUES (:assisted, :referent, 'madre', 1, 'archiviata', CURRENT_TIMESTAMP)
                """),
                {'assisted': assisted_id, 'referent': referent_id},
            )


def test_named_fks_and_indexes_match_between_orm_source_and_migration_source():
    app_source = (PROJECT_ROOT / 'app.py').read_text()
    migration_source = A1_MIGRATION.read_text()
    names = {
        'fk_appuntamento_persona_v2',
        'fk_call_sonno_persona_v2',
        'fk_iscrizione_corso_persona_v2',
        'fk_persona_legacy_persona_corso',
        'fk_recapito_persona_persona',
        'fk_relazione_persona_assistita',
        'fk_relazione_persona_referente',
        'fk_segnalazione_duplicato_persona_a',
        'fk_segnalazione_duplicato_persona_b',
        'fk_fusione_persona_principale',
        'fk_fusione_persona_secondaria',
        'fk_fusione_persona_admin',
        'ix_relazione_persona_assistita_id',
        'ix_relazione_persona_referente_id',
        'ix_fusione_persona_principale_id',
        'ix_fusione_persona_secondaria_id',
    }
    for name in names:
        assert name in app_source, name
        assert name in migration_source, name

    for name in {
        'fk_appuntamento_persona_v2',
        'fk_call_sonno_persona_v2',
        'fk_iscrizione_corso_persona_v2',
    }:
        orm_fragment = re.search(rf"ForeignKey\([^\n]+name='{name}'[^\n]+", app_source)
        assert orm_fragment and "ondelete='RESTRICT'" in orm_fragment.group(0)
    assert "ondelete='RESTRICT'" in migration_source
    assert 'ON DELETE RESTRICT' in migration_source


def test_a4_operational_flows_use_only_patients_v2_writes():
    """The direct cutover must not create new legacy patient/link rows."""

    source = (PROJECT_ROOT / 'app.py').read_text()
    tree = ast.parse(source)
    constructor_calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {'PersonaCorso', 'CollegamentoPersona'}
    ]

    assert constructor_calls == []
    assert 'appointment.persona_v2 = patient' in source
    assert 'registration.persona_v2 = patient' in source
    assert 'persona_v2=persona' in source
