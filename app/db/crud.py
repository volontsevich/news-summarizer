
# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""CRUD operations for models."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence
from sqlalchemy import select, update, insert, func, desc, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from .models import Channel, Post, FilterRule, AlertRule, Digest, Processed

def upsert_channel_by_handle(db: Session, handle: str, title: str) -> Channel:
	"""Insert or update a channel by username (handle)."""
	stmt = pg_insert(Channel).values(
		username=handle,
		name=title,
		created_at=datetime.now(timezone.utc),
		updated_at=datetime.now(timezone.utc)
	)
	stmt = stmt.on_conflict_do_update(
		index_elements=[Channel.username],
		set_={"name": title, "updated_at": datetime.now(timezone.utc)}
	)
	stmt = stmt.returning(Channel)
	result = db.execute(stmt)
	db.commit()
	return result.scalar_one()

def create_channel(db: Session, username: str, name: str, description: str = None) -> Channel:
	"""Create a new channel."""
	channel = Channel(
		username=username,
		name=name,
		description=description,
		is_active=True
	)
	db.add(channel)
	db.commit()
	db.refresh(channel)
	return channel

def save_posts_batch_with_dedupe(db: Session, posts: List[dict]) -> List[Post]:
	"""Bulk insert posts, deduplicating on (channel_id, message_id). Returns inserted posts."""
	if not posts:
		return []
	stmt = pg_insert(Post).values(posts)
	stmt = stmt.on_conflict_do_nothing(index_elements=[Post.channel_id, Post.message_id])
	db.execute(stmt)
	db.commit()
	# Return all posts that match the channel_id and message_id combinations
	conditions = []
	for p in posts:
		conditions.append(
			(Post.channel_id == p["channel_id"]) & (Post.message_id == p["message_id"])
		)
	
	if conditions:
		q = select(Post).where(or_(*conditions))
		return list(db.scalars(q))
	return []

def get_new_posts_for_channel(db: Session, channel_id: uuid.UUID, after_message_id: Optional[int]=None) -> List[Post]:
	"""Get new posts for a channel after a given message_id."""
	q = select(Post).where(Post.channel_id == channel_id)
	if after_message_id is not None:
		q = q.where(Post.message_id > after_message_id)
	q = q.order_by(Post.message_id.asc())
	return list(db.scalars(q))

def mark_channel_last_message_id(db: Session, channel_id: uuid.UUID, last_message_id: int) -> None:
	"""Update channel's last_message_id and updated_at."""
	db.execute(
		update(Channel)
		.where(Channel.id == channel_id)
		.values(updated_at=datetime.now(timezone.utc))
	)
	db.commit()

def list_enabled_channels(db: Session) -> List[Channel]:
	"""List all enabled channels."""
	q = select(Channel).where(Channel.is_active == True).order_by(Channel.username.asc())
	return list(db.scalars(q))

def list_rules(db: Session, rule_type: str = "filter", enabled_only: bool = True) -> Sequence:
	"""List filter or alert rules."""
	if rule_type == "filter":
		model = FilterRule
	elif rule_type == "alert":
		model = AlertRule
	else:
		raise ValueError("rule_type must be 'filter' or 'alert'")
	q = select(model)
	if enabled_only:
		q = q.where(model.enabled == True)
	q = q.order_by(model.created_at.desc())
	return list(db.scalars(q))

def save_processed_flags(db: Session, post_id: uuid.UUID, blocked: bool, matched_alerts: Optional[list] = None) -> Processed:
	"""Upsert processed flags for a post."""
	matched_alerts = matched_alerts or []
	stmt = pg_insert(Processed).values(
		post_id=post_id, blocked=blocked, matched_alerts=matched_alerts
	).on_conflict_do_update(
		index_elements=[Processed.post_id],
		set_={"blocked": blocked, "matched_alerts": matched_alerts}
	).returning(Processed)
	result = db.execute(stmt)
	db.commit()
	return result.scalar_one()

def save_digest(db: Session, timeframe_start: datetime, timeframe_end: datetime, language: str, summary_md: str) -> Digest:
	"""Save a digest for a timeframe and language."""
	digest = Digest(
		timeframe_start=timeframe_start,
		timeframe_end=timeframe_end,
		language=language,
		summary_md=summary_md,
		created_at=datetime.now(timezone.utc),
	)
	db.add(digest)
	db.commit()
	db.refresh(digest)
	return digest

def get_last_hour_posts(db: Session, channel_id: Optional[uuid.UUID] = None, language: Optional[str] = None) -> List[Post]:
	"""Get posts from the last hour, optionally filtered by channel and language."""
	now = datetime.now(timezone.utc)
	hour_ago = now - timedelta(hours=1)
	q = select(Post).where(Post.posted_at >= hour_ago)
	if channel_id:
		q = q.where(Post.channel_id == channel_id)
	if language:
		q = q.where(Post.language == language)
	q = q.order_by(Post.posted_at.asc())
	return list(db.scalars(q))

def get_latest_digest(db: Session, language: Optional[str] = None) -> Optional[Digest]:
	"""Get the latest digest, optionally filtered by language."""
	q = select(Digest)
	if language:
		q = q.where(Digest.language == language)
	q = q.order_by(Digest.created_at.desc())
	return db.scalars(q).first()
