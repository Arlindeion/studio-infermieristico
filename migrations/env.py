import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


# SQLite does not reflect names or ON DELETE options for foreign keys added as
# inline columns. PAZ-A1 tests these exact constraints through PRAGMA and real
# writes; excluding only these known reflection artifacts keeps ``db check``
# useful for every other object.
SQLITE_INLINE_PATIENT_FOREIGN_KEYS = {
    ('appuntamento', ('persona_id',), ('persona.id',)),
    ('call_sonno', ('persona_id',), ('persona.id',)),
    ('iscrizione_corso', ('persona_v2_id',), ('persona.id',)),
}


def _foreign_key_signature(foreign_key):
    return (
        foreign_key.table.name,
        tuple(element.parent.name for element in foreign_key.elements),
        tuple(element.target_fullname for element in foreign_key.elements),
    )


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = dict(current_app.extensions['migrate'].configure_args)
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        configured_include_object = conf_args.get('include_object')

        def include_object(obj, name, type_, reflected, compare_to):
            if configured_include_object is not None and not configured_include_object(
                obj,
                name,
                type_,
                reflected,
                compare_to,
            ):
                return False
            if (
                connection.dialect.name == 'sqlite'
                and type_ == 'foreign_key_constraint'
                and _foreign_key_signature(obj) in SQLITE_INLINE_PATIENT_FOREIGN_KEYS
            ):
                return False
            return True

        conf_args['include_object'] = include_object
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
