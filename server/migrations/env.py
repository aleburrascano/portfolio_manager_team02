"""
Alembic environment.

The database URL and the model metadata both come from the app itself, so
migrations always run against whatever DATABASE_URL points at, and
`alembic check` can compare the models to the migration history.
"""
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from db.connection import database_url
from db.models import Base

load_dotenv()

config = context.config
# Escaped because ConfigParser treats a bare % as interpolation, and URL
# encoded passwords contain them.
config.set_main_option('sqlalchemy.url', database_url().replace('%', '%%'))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for `alembic upgrade --sql`."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most things in place; batch mode rebuilds
            # the table instead, so one migration runs on both backends.
            render_as_batch=connection.dialect.name == 'sqlite',
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
