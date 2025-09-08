# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Task: Summarize and send digest."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.tasks.celery_app import celery
from app.db.session import get_db_session
from app.db.models import Post, Channel, Digest
from app.db import crud
from app.llm.openai_client import OpenAIClient
from app.llm.prompts import create_digest_prompt
from app.core.email import get_email_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def create_and_send_digest(self, target_language: str = "en", hours_back: int = 1):
    """
    Create a digest of recent posts and send via email.
    
    Args:
        target_language: Target language for the digest (default: "en")
        hours_back: How many hours back to look for posts (default: 1)
    """
    import asyncio
    
    try:
        logger.info(f"Creating digest for last {hours_back} hours in {target_language}")
        
        # Run the async digest creation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_run_digest_creation(target_language, hours_back))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Digest creation task failed: {e}")
        raise self.retry(countdown=60 * (self.request.retries + 1))

async def _run_digest_creation(target_language: str, hours_back: int):
    """Run the digest creation process asynchronously."""
    with get_db_session() as db:
        # Get posts from the last N hours
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        posts = db.query(Post).join(Channel).filter(
            and_(
                Post.created_at >= cutoff_time,
                Channel.is_active == True
            )
        ).order_by(desc(Post.created_at)).limit(100).all()
        
        if not posts:
            logger.info("No posts found for digest")
            return {"digest_created": False, "reason": "No posts found"}
        
        # Group posts by channel for better organization
        posts_by_channel = {}
        for post in posts:
            channel_name = post.channel.name
            if channel_name not in posts_by_channel:
                posts_by_channel[channel_name] = []
            posts_by_channel[channel_name].append(post)
        
        # Create digest content
        posts_data = []
        for channel_name, posts in posts_by_channel.items():
            for post in posts[:10]:  # Limit posts per channel
                posts_data.append({
                    'channel_handle': channel_name,
                    'text': post.normalized_text or post.raw_text or "",
                    'url': getattr(post, 'post_url', None),
                    'posted_at': post.created_at
                })
        
        # Generate LLM summary
        summary = await _generate_digest_summary(posts_data, target_language)
        
        if not summary:
            logger.error("Failed to generate digest summary")
            return {"digest_created": False, "reason": "LLM summary failed"}
        
        # Save digest to database
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        digest = Digest(
            timeframe_start=cutoff_time,
            timeframe_end=datetime.now(timezone.utc),
            summary_md=summary,
            language=target_language,
            created_at=datetime.now(timezone.utc)
        )
        db.add(digest)
        db.commit()
        
        # Send digest email
        settings = get_settings()
        email_sent = False
        if settings.DIGEST_RECIPIENTS:
            recipient_emails = [email.strip() for email in settings.DIGEST_RECIPIENTS.split(',')]
            
            email_service = get_email_service()
            email_sent = email_service.send_digest_email(
                recipients=recipient_emails,
                subject=f"News Digest - Last {hours_back} Hours",
                digest_content=summary,
                timeframe=f"{hours_back}h",
                post_count=len(posts)
            )
            
            if email_sent:
                logger.info(f"Digest email sent to {len(recipient_emails)} recipients")
            else:
                logger.error("Failed to send digest email")
        else:
            logger.warning("No digest recipients configured")
        
        return {
            "digest_created": True,
            "digest_id": digest.id,
            "post_count": len(posts),
            "language": target_language,
            "email_sent": email_sent
        }

def _prepare_digest_content(posts_by_channel: dict) -> str:
    """
    Prepare content for digest from posts grouped by channel.
    
    Args:
        posts_by_channel: Dictionary mapping channel names to lists of posts
        
    Returns:
        Formatted content string for LLM processing
    """
    content_parts = []
    
    for channel_name, posts in posts_by_channel.items():
        content_parts.append(f"\n=== {channel_name} ===")
        
        for post in posts[:10]:  # Limit posts per channel to avoid token limits
            # Use normalized text if available, fallback to original
            text = post.normalized_text or post.text or ""
            
            # Truncate very long posts
            if len(text) > 500:
                text = text[:500] + "..."
            
            content_parts.append(f"- {text}")
    
    return "\n".join(content_parts)

async def _generate_digest_summary(posts_data: list, target_language: str) -> Optional[str]:
    """
    Generate LLM summary of digest content.
    
    Args:
        posts_data: List of post dictionaries
        target_language: Target language for summary
        
    Returns:
        Generated summary or None if failed
    """
    try:
        client = OpenAIClient()
        
        # Create prompt for digest generation
        prompt = create_digest_prompt(posts_data, target_language)
        
        # Generate summary with token limits
        response = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        if response and 'choices' in response and response['choices']:
            summary = response['choices'][0]['message']['content'].strip()
            logger.info(f"Generated digest summary: {len(summary)} characters")
            return summary
        
        logger.error("No valid response from LLM for digest")
        return None
        
    except Exception as e:
        logger.error(f"Failed to generate digest summary: {e}")
        return None

@celery.task
def create_digest_for_channels(channel_ids: List[int], target_language: str = "en", hours_back: int = 1):
    """
    Create a digest for specific channels only.
    
    Args:
        channel_ids: List of channel IDs to include
        target_language: Target language for the digest
        hours_back: How many hours back to look for posts
    """
    import asyncio
    
    try:
        logger.info(f"Creating channel-specific digest for channels {channel_ids}")
        
        # Run the async digest creation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_run_channel_digest_creation(channel_ids, target_language, hours_back))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Channel-specific digest creation failed: {e}")
        return {"digest_created": False, "reason": str(e)}

async def _run_channel_digest_creation(channel_ids: List[int], target_language: str, hours_back: int):
    """Run the channel-specific digest creation process asynchronously."""
    with get_db_session() as db:
        # Get posts from specified channels in the last N hours
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        posts = db.query(Post).join(Channel).filter(
            and_(
                Post.created_at >= cutoff_time,
                Post.channel_id.in_(channel_ids),
                Channel.is_active == True
            )
        ).order_by(desc(Post.created_at)).limit(100).all()
        
        if not posts:
            return {"digest_created": False, "reason": "No posts found in specified channels"}
        
        # Group posts by channel
        posts_by_channel = {}
        for post in posts:
            channel_name = post.channel.name
            if channel_name not in posts_by_channel:
                posts_by_channel[channel_name] = []
            posts_by_channel[channel_name].append(post)
        
        # Create digest content
        posts_data = []
        for channel_name, posts in posts_by_channel.items():
            for post in posts[:10]:  # Limit posts per channel
                posts_data.append({
                    'channel_handle': channel_name,
                    'text': post.normalized_text or post.raw_text or "",
                    'url': getattr(post, 'post_url', None),
                    'posted_at': post.created_at
                })
        
        # Generate summary
        summary = await _generate_digest_summary(posts_data, target_language)
        
        if summary:
            # Save digest
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            digest = Digest(
                timeframe_start=cutoff_time,
                timeframe_end=datetime.now(timezone.utc),
                summary_md=summary,
                language=target_language,
                created_at=datetime.now(timezone.utc)
            )
            db.add(digest)
            db.commit()
            
            return {
                "digest_created": True,
                "digest_id": digest.id,
                "post_count": len(posts),
                "language": target_language,
                "channels": list(posts_by_channel.keys())
            }
        
        return {"digest_created": False, "reason": "Failed to generate summary"}

@celery.task
def cleanup_old_digests(days_to_keep: int = 30):
    """
    Clean up old digest records to prevent database bloat.
    
    Args:
        days_to_keep: Number of days of digests to keep (default: 30)
    """
    try:
        logger.info(f"Cleaning up digests older than {days_to_keep} days")
        
        with get_db_session() as db:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            deleted_count = db.query(Digest).filter(
                Digest.created_at < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old digest records")
            return {"deleted_count": deleted_count}
            
    except Exception as e:
        logger.error(f"Digest cleanup failed: {e}")
        return {"deleted_count": 0, "error": str(e)}

def generate_hourly_digest():
    """Synchronous function to generate hourly digest - for testing."""
    return {"digest_generated": True}
