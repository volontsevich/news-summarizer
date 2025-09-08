
# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""ORM models for Telegram posts, channels, filters, alerts, digests."""


import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
	Column, String, Boolean, Integer, DateTime, Text, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON as BaseJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base

Base = declarative_base()

def utcnow() -> datetime:
	return datetime.now(timezone.utc)

class Channel(Base):
	__tablename__ = "channels"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
	name: Mapped[str] = mapped_column(String(256), nullable=False)
	description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
	posts = relationship("Post", back_populates="channel")

class Post(Base):
	__tablename__ = "posts"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
	message_id: Mapped[int] = mapped_column(Integer, nullable=False)
	posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	raw_text: Mapped[str] = mapped_column(Text, nullable=False)
	language: Mapped[str] = mapped_column(String(16), nullable=False)
	normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
	url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
	channel = relationship("Channel", back_populates="posts")
	processed = relationship("Processed", back_populates="post", uselist=False)
	__table_args__ = (
		UniqueConstraint("channel_id", "message_id", name="uq_channel_message"),
		Index("ix_posts_channel_id_message_id", "channel_id", "message_id"),
	)

class FilterRule(Base):
	__tablename__ = "filter_rules"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	name: Mapped[str] = mapped_column(String(128), nullable=False)
	pattern: Mapped[str] = mapped_column(String(512), nullable=False)
	is_regex: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
	language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
	is_blocklist: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
	enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
	__table_args__ = (
		Index("ix_filter_rules_pattern", "pattern"),
		Index("ix_filter_rules_language", "language"),
	)

class AlertRule(Base):
	__tablename__ = "alert_rules"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	name: Mapped[str] = mapped_column(String(128), nullable=False)
	pattern: Mapped[str] = mapped_column(String(512), nullable=False)
	is_regex: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
	language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
	enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
	email_to: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
	__table_args__ = (
		Index("ix_alert_rules_pattern", "pattern"),
		Index("ix_alert_rules_language", "language"),
	)

class Digest(Base):
	__tablename__ = "digests"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	timeframe_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	timeframe_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	language: Mapped[str] = mapped_column(String(16), nullable=False)
	summary_md: Mapped[str] = mapped_column(Text, nullable=False)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
	__table_args__ = (
		Index("ix_digests_timeframe", "timeframe_start", "timeframe_end"),
		Index("ix_digests_language", "language"),
	)


class Processed(Base):
	__tablename__ = "processed"
	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), unique=True, nullable=False)
	blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
	matched_alerts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
	post = relationship("Post", back_populates="processed")
	__table_args__ = (
		Index("ix_processed_blocked", "blocked"),
	)