
# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Alembic environment setup."""

import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import app settings and models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.config import get_settings
from app.db import models

# Alembic Config object, provides access to .ini values
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Set SQLAlchemy URL from app config
settings = get_settings()
config.set_main_option('sqlalchemy.url', settings.sqlalchemy_dsn())

target_metadata = models.Base.metadata

def run_migrations_offline():
	url = config.get_main_option("sqlalchemy.url")
	context.configure(
		url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
	)
	with context.begin_transaction():
		context.run_migrations()

def run_migrations_online():
	connectable = engine_from_config(
		config.get_section(config.config_ini_section),
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)
	with connectable.connect() as connection:
		context.configure(
			connection=connection, target_metadata=target_metadata, compare_type=True
		)
		with context.begin_transaction():
			context.run_migrations()

if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
