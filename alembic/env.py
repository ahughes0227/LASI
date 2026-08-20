"""Alembic environment for LASI operational memory."""

import os
from logging.config import fileConfig

from alembic import context
from services.memory import models  # noqa: F401
from services.memory.database import Base
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

# The ini file names a local SQLite database.  `LASI_DATABASE_URL` is what the
# application already reads (`services.admin.service`), and without honouring it here a
# migration silently runs against the developer's local file no matter which database the
# rest of the system is pointed at -- including when that database is PostgreSQL.
_database_url = os.environ.get("LASI_DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
