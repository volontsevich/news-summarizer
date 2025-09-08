
# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""App settings and config loader."""

from functools import lru_cache
from typing import Optional
from pydantic import Field, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	# Telegram
	TELEGRAM_API_ID: Optional[str] = Field(default=None)
	TELEGRAM_API_HASH: Optional[str] = Field(default=None)
	TELEGRAM_SESSION_NAME: str = Field(default="tg_news_session")
	TELEGRAM_TIMEOUT: int = Field(default=20)
	TELEGRAM_RATE_LIMIT_SLEEP: float = Field(default=1.2)

	# Database
	DB_HOST: str = Field(default="db")
	DB_PORT: int = Field(default=5432)
	DB_USER: str = Field(default="postgres")
	DB_PASSWORD: str = Field(default="postgres")
	DB_NAME: str = Field(default="tgnews")

	# Redis
	REDIS_URL: str = Field(default="redis://redis:6379/0")

	# OpenAI
	OPENAI_API_KEY: Optional[str] = Field(default=None)
	SUMMARY_TARGET_LANG: str = Field(default="en")
	SUMMARY_MODEL: str = Field(default="gpt-4o-mini")
	SUMMARY_MAX_TOKENS: int = Field(default=800)

	# Scheduling
	ALERT_POLL_CRON: str = Field(default="*/5 * * * *")
	DIGEST_CRON: str = Field(default="0 * * * *")
	TIMEZONE: str = Field(default="UTC")

	# SMTP
	SMTP_HOST: Optional[str] = Field(default=None)
	SMTP_PORT: int = Field(default=587)
	SMTP_USERNAME: Optional[str] = Field(default=None)
	SMTP_PASSWORD: Optional[str] = Field(default=None)
	SMTP_TLS: bool = Field(default=True)
	SMTP_FROM_EMAIL: str = Field(default="TG Summarizer <no-reply@example.com>")
	DIGEST_RECIPIENTS: Optional[str] = Field(default=None)  # Comma-separated emails

	# API Authentication
	API_USERNAME: Optional[str] = Field(default=None)
	API_PASSWORD: Optional[str] = Field(default=None)
	DEBUG: bool = Field(default=False)

	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

	def sqlalchemy_dsn(self) -> str:
		"""Return SQLAlchemy DSN for Postgres."""
		return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

	def target_language(self) -> str:
		"""Return the target language for summaries."""
		return self.SUMMARY_TARGET_LANG or "en"

	def get_alert_cron(self) -> str:
		return self.ALERT_POLL_CRON

	def get_digest_cron(self) -> str:
		return self.DIGEST_CRON

	def require_openai(self) -> bool:
		"""Check if OpenAI configuration is complete."""
		return bool(self.OPENAI_API_KEY)

	def require_smtp(self) -> bool:
		"""Check if SMTP configuration is complete."""
		return bool(
			self.SMTP_HOST and 
			self.SMTP_USERNAME and 
			self.SMTP_PASSWORD and 
			self.SMTP_FROM_EMAIL
		)

	def get_digest_recipients(self) -> list[str]:
		"""Get list of digest recipients."""
		if not self.DIGEST_RECIPIENTS:
			return []
		return [email.strip() for email in self.DIGEST_RECIPIENTS.split(",") if email.strip()]

@lru_cache(maxsize=1)
def get_settings() -> Settings:
	"""Return cached settings instance."""
	return Settings()

