from logging.config import fileConfig
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure project root is on sys.path
root_path = Path(__file__).resolve().parents[4]
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from settings
config.set_main_option("sqlalchemy.url", settings.platform_db_url)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="harness",
        include_schemas=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="harness",
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
