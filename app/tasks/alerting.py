# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Task: Alert on matching posts."""

import logging
import re
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.tasks.celery_app import celery
from app.db.session import get_db_session
from app.db.models import Post, AlertRule, Channel
from app.core.email import get_email_service

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def check_post_for_alerts(self, post_id: int):
    """
    Check a post against all alert rules and send notifications.
    
    Args:
        post_id: ID of the post to check
    """
    try:
        logger.info(f"Checking post {post_id} for alerts")
        
        with get_db_session() as db:
            # Get the post
            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                logger.warning(f"Post {post_id} not found")
                return {"alerts_triggered": 0}
            
            # Get the channel
            channel = db.query(Channel).filter(Channel.id == post.channel_id).first()
            if not channel:
                logger.warning(f"Channel {post.channel_id} not found for post {post_id}")
                return {"alerts_triggered": 0}
            
            # Get active alert rules
            alert_rules = db.query(AlertRule).filter(
                and_(
                    AlertRule.is_active == True,
                    # Either channel-specific or global rules
                    (AlertRule.channel_id == post.channel_id) | (AlertRule.channel_id.is_(None))
                )
            ).all()
            
            if not alert_rules:
                logger.debug(f"No alert rules found for post {post_id}")
                return {"alerts_triggered": 0}
            
            alerts_triggered = 0
            
            # Check each rule
            for rule in alert_rules:
                try:
                    if _check_rule_match(post, rule):
                        _send_alert_notification(db, post, channel, rule)
                        alerts_triggered += 1
                        logger.info(f"Alert triggered: {rule.name} for post {post_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to process alert rule {rule.name}: {e}")
                    continue
            
            return {"alerts_triggered": alerts_triggered}
            
    except Exception as e:
        logger.error(f"Alert checking task failed for post {post_id}: {e}")
        raise self.retry(countdown=30 * (self.request.retries + 1))

def _check_rule_match(post: Post, rule: AlertRule) -> bool:
    """
    Check if a post matches an alert rule.
    
    Args:
        post: Post model instance
        rule: AlertRule model instance
        
    Returns:
        True if post matches the rule, False otherwise
    """
    # Use normalized text for better matching
    text_to_check = (post.normalized_text or post.text or '').lower()
    
    if rule.rule_type == 'keyword':
        # Check for keyword matches
        keywords = [kw.strip().lower() for kw in rule.pattern.split(',')]
        return any(keyword in text_to_check for keyword in keywords)
        
    elif rule.rule_type == 'regex':
        # Check for regex matches
        try:
            return bool(re.search(rule.pattern, text_to_check, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"Invalid regex pattern in alert rule {rule.name}: {rule.pattern} - {e}")
            return False
            
    elif rule.rule_type == 'language':
        # Check for language matches
        if not post.detected_language:
            return False
        return post.detected_language.lower() == rule.pattern.lower()
        
    else:
        logger.warning(f"Unknown alert rule type: {rule.rule_type}")
        return False

def _send_alert_notification(db: Session, post: Post, channel: Channel, rule: AlertRule):
    """
    Send alert notification for a matching post.
    
    Args:
        db: Database session
        post: Post model instance
        channel: Channel model instance
        rule: AlertRule model instance
    """
    try:
        # Parse recipient emails
        recipient_emails = [email.strip() for email in rule.recipient_emails.split(',') if email.strip()]
        
        if not recipient_emails:
            logger.warning(f"No recipient emails configured for alert rule {rule.name}")
            return
        
        # Prepare post content for email
        post_title = _extract_post_title(post.text)
        post_content = post.text[:1000] + "..." if len(post.text) > 1000 else post.text
        
        # Send alert email
        email_service = get_email_service()
        success = email_service.send_alert_email(
            recipients=recipient_emails,
            subject=f"Alert: {rule.name}",
            alert_content=post_content,
            matched_rules=[rule.name],
            post_url=post.post_url or f"t.me/{channel.username}/{post.message_id}"
        )
        
        if success:
            logger.info(f"Alert email sent for rule {rule.name} to {len(recipient_emails)} recipients")
        else:
            logger.error(f"Failed to send alert email for rule {rule.name}")
            
    except Exception as e:
        logger.error(f"Failed to send alert notification: {e}")
        raise

def _extract_post_title(text: str) -> str:
    """
    Extract a title from post text (first line or sentence).
    
    Args:
        text: Post text
        
    Returns:
        Extracted title (max 100 characters)
    """
    if not text:
        return "No title"
    
    # Try to get first line
    lines = text.strip().split('\n')
    first_line = lines[0].strip()
    
    if first_line:
        # Truncate if too long
        title = first_line[:100] + "..." if len(first_line) > 100 else first_line
        return title
    
    # Fallback to first sentence
    sentences = text.split('.')
    if sentences and sentences[0].strip():
        sentence = sentences[0].strip()
        title = sentence[:100] + "..." if len(sentence) > 100 else sentence
        return title
    
    # Final fallback
    return text[:50] + "..." if len(text) > 50 else text

@celery.task
def test_alert_rule(rule_id: int, test_text: str) -> dict:
    """
    Test an alert rule against sample text.
    
    Args:
        rule_id: ID of the alert rule to test
        test_text: Sample text to test against
        
    Returns:
        Dictionary with test results
    """
    try:
        with get_db_session() as db:
            rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
            if not rule:
                return {"error": "Alert rule not found"}
            
            # Create a temporary post object for testing
            class TestPost:
                def __init__(self, text: str):
                    self.text = text
                    self.normalized_text = text.lower().strip()
                    self.detected_language = "en"  # Default for testing
            
            test_post = TestPost(test_text)
            match_result = _check_rule_match(test_post, rule)
            
            return {
                "rule_name": rule.name,
                "rule_type": rule.rule_type,
                "pattern": rule.pattern,
                "test_text": test_text,
                "matches": match_result
            }
            
    except Exception as e:
        logger.error(f"Failed to test alert rule {rule_id}: {e}")
        return {"error": str(e)}
