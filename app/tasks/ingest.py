# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Task: Ingest Telegram posts."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.tasks.celery_app import celery
from app.db.session import get_db_session
from app.db.models import Channel, Post, FilterRule, Processed
from app.ingestion.telegram_client import TelegramClientFactory, fetch_new_posts
from app.ingestion.normalizer import normalize_text
from app.ingestion.language import detect_language_safe
from app.tasks.alerting import check_post_for_alerts

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def ingest_telegram_posts(self, channel_id: Optional[int] = None):
    """
    Ingest new posts from Telegram channels.
    
    Args:
        channel_id: Optional specific channel ID to ingest. If None, ingest all active channels.
    """
    import asyncio
    
    try:
        logger.info(f"Starting post ingestion for channel_id={channel_id}")
        
        # Run the async ingestion in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_run_ingestion(channel_id))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Ingestion task failed: {e}")
        raise self.retry(countdown=60 * (self.request.retries + 1))

async def _run_ingestion(channel_id: Optional[int] = None):
    """Run the ingestion process asynchronously."""
    with get_db_session() as db:
        # Get channels to process
        if channel_id:
            channels = db.query(Channel).filter(
                and_(Channel.id == channel_id, Channel.is_active == True)
            ).all()
        else:
            channels = db.query(Channel).filter(Channel.is_active == True).all()
        
        if not channels:
            logger.warning(f"No active channels found for channel_id={channel_id}")
            return {"processed_channels": 0, "new_posts": 0}
        
        total_new_posts = 0
        
        # Process each channel
        for channel in channels:
            try:
                new_posts = await _ingest_channel_posts(db, channel)
                total_new_posts += new_posts
                logger.info(f"Ingested {new_posts} new posts from channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Failed to ingest posts from channel {channel.name}: {e}")
                continue
        
        db.commit()
        
        result = {
            "processed_channels": len(channels),
            "new_posts": total_new_posts
        }
        
        logger.info(f"Ingestion completed: {result}")
        return result

async def _ingest_channel_posts(db: Session, channel: Channel) -> int:
    """
    Ingest posts from a specific channel.
    
    Args:
        db: Database session
        channel: Channel model instance
        
    Returns:
        Number of new posts ingested
    """
    
    try:
        # Get the last processed message ID for this channel by finding max message_id
        max_message_result = db.query(func.max(Post.message_id)).filter(
            Post.channel_id == channel.id
        ).scalar()
        
        last_message_id = max_message_result if max_message_result else 0
        
        # Fetch new posts from Telegram
        posts_data = await fetch_new_posts(
            channel.username,
            last_message_id=last_message_id,
            limit=100
        )
        
        if not posts_data:
            return 0
        
        # Filter rules for this channel
        filter_rules = db.query(FilterRule).filter(
            and_(
                FilterRule.channel_id == channel.id,
                FilterRule.is_active == True
            )
        ).all()
        
        new_posts_count = 0
        latest_message_id = last_message_id
        
        for post_data in posts_data:
            try:
                # Check if post should be filtered out
                if _should_filter_post(post_data, filter_rules):
                    logger.debug(f"Filtered out post {post_data['message_id']} from {channel.name}")
                    continue
                
                # Normalize and detect language
                normalized_text = normalize_text(post_data.get('text', ''))
                # Detect language
                detected_language = detect_language_safe(normalized_text)
                
                # Create post record
                post = Post(
                    channel_id=channel.id,
                    message_id=post_data['message_id'],
                    text=post_data.get('text', ''),
                    normalized_text=normalized_text,
                    detected_language=detected_language,
                    post_date=post_data.get('date', datetime.now(timezone.utc)),
                    post_url=post_data.get('url', ''),
                    media_type=post_data.get('media_type'),
                    created_at=datetime.now(timezone.utc)
                )
                
                db.add(post)
                db.flush()  # Get the post ID
                
                # Check for alerts asynchronously
                check_post_for_alerts.delay(post.id)
                
                new_posts_count += 1
                latest_message_id = max(latest_message_id, post_data['message_id'])
                
            except Exception as e:
                logger.error(f"Failed to process post {post_data.get('message_id')}: {e}")
                continue
        
        # Log processing completion
        logger.info(f"Processed {new_posts_count} new posts from {channel.name}")
        
        return new_posts_count
        
    except Exception as e:
        logger.error(f"Failed to ingest from channel {channel.name}: {e}")
        raise

def _should_filter_post(post_data: dict, filter_rules: List[FilterRule]) -> bool:
    """
    Check if a post should be filtered out based on filter rules.
    
    Args:
        post_data: Post data from Telegram
        filter_rules: List of filter rules for the channel
        
    Returns:
        True if post should be filtered out, False otherwise
    """
    if not filter_rules:
        return False
    
    post_text = post_data.get('text', '').lower()
    
    for rule in filter_rules:
        if rule.rule_type == 'keyword':
            keywords = [kw.strip().lower() for kw in rule.pattern.split(',')]
            if any(keyword in post_text for keyword in keywords):
                logger.debug(f"Post filtered by keyword rule: {rule.pattern}")
                return True
                
        elif rule.rule_type == 'regex':
            import re
            try:
                if re.search(rule.pattern, post_text, re.IGNORECASE):
                    logger.debug(f"Post filtered by regex rule: {rule.pattern}")
                    return True
            except re.error:
                logger.warning(f"Invalid regex pattern in filter rule: {rule.pattern}")
                continue
    
    return False

@celery.task(bind=True)
def ingest_single_channel(self, channel_id: int):
    """
    Ingest posts from a single channel.
    
    Args:
        channel_id: ID of the channel to ingest
    """
    return ingest_telegram_posts.delay(channel_id=channel_id)

def ingest_new_posts():
    """Synchronous function to ingest new posts - for testing."""
    return ingest_telegram_posts.apply().result
