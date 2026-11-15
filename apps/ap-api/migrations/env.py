from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool, inspect, text
from asaa_ap.config import get_settings
from asaa_ap.database import Base
from asaa_ap import models  # noqa: F401
from asaa_ap import procurement_models  # noqa: F401
from asaa_people import models as people_models  # noqa: F401
from asaa_governance import models as governance_models  # noqa: F401
from asaa_governance import authority as authority_models  # noqa: F401
from asaa_governance import administration as administration_models  # noqa: F401
from asaa_governance import authorization as authorization_models  # noqa: F401
from asaa_workforce_finance import models as workforce_finance_models  # noqa: F401
from asaa_identity import models as identity_models  # noqa: F401
from asaa_notifications import models as notification_models  # noqa: F401
from asaa_registers import models as register_models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def ensure_postgresql_revision_column_capacity(connection):
    if connection.dialect.name != "postgresql":
        return
    if "alembic_version" not in inspect(connection).get_table_names():
        connection.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
        ))
    else:
        connection.execute(text(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
        ))


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        with connection.begin():
            ensure_postgresql_revision_column_capacity(connection)
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
