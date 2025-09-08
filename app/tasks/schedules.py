# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Celery beat schedule definitions."""

import logging
from celery.schedules import crontab
from app.core.config import get_settings

logger = logging.getLogger(__name__)

def create_beat_schedule() -> dict:
    """
    Create Celery beat schedule from environment configuration.
    
    Returns:
        Dictionary containing beat schedule configuration
    """
    settings = get_settings()
    
    # Parse cron expressions
    alert_cron = settings.get_alert_cron()  # Default: */5 * * * *
    digest_cron = settings.get_digest_cron()  # Default: 0 * * * *
    timezone = settings.TIMEZONE  # Default: UTC
    
    logger.info(f"Creating beat schedule with timezone: {timezone}")
    logger.info(f"Alert/Ingest cron: {alert_cron}")
    logger.info(f"Digest cron: {digest_cron}")
    
    # Parse cron expressions into crontab objects
    alert_schedule = parse_cron_expression(alert_cron, timezone)
    digest_schedule = parse_cron_expression(digest_cron, timezone)
    
    schedule = {
        # Ingest new posts from Telegram channels
        'ingest-new-posts': {
            'task': 'app.tasks.ingest.ingest_new_posts',
            'schedule': alert_schedule,
            'options': {
                'queue': 'ingest',
                'routing_key': 'ingest'
            }
        },
        
        # Process alerts on new posts
        'run-alerts': {
            'task': 'app.tasks.alerting.run_alerts',
            'schedule': alert_schedule,
            'options': {
                'queue': 'alerts',
                'routing_key': 'alerts'
            }
        },
        
        # Build hourly digest
        'build-hourly-digest': {
            'task': 'app.tasks.digest.build_hourly_digest',
            'schedule': digest_schedule,
            'options': {
                'queue': 'digest',
                'routing_key': 'digest'
            }
        },
        
        # Health check task (every 10 minutes)
        'health-check': {
            'task': 'health_check',
            'schedule': crontab(minute='*/10'),
            'options': {
                'queue': 'default',
                'routing_key': 'default'
            }
        }
    }
    
    logger.info(f"Created beat schedule with {len(schedule)} tasks")
    return schedule

def parse_cron_expression(cron_expr: str, timezone: str) -> crontab:

    try:
        # Split cron expression into components
        parts = cron_expr.strip().split()
        
        if len(parts) != 5:
            logger.error(f"Invalid cron expression '{cron_expr}', expected 5 parts, got {len(parts)}")
            # Fallback to every 5 minutes
            return crontab(minute='*/5')
        
        minute, hour, day_of_month, month, day_of_week = parts
        
        # Create crontab object (timezone not supported in this Celery version)
        schedule = crontab(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month
        )
        
        logger.debug(f"Parsed cron '{cron_expr}' -> {schedule}")
        return schedule
        
    except Exception as e:
        logger.error(f"Failed to parse cron expression '{cron_expr}': {e}")
        # Fallback to every 5 minutes
        logger.warning("Using fallback schedule: every 5 minutes")
        return crontab(minute='*/5')

def validate_timezone(timezone_str: str) -> bool:
    """
    Validate that a timezone string is valid.
    
    Args:
        timezone_str: Timezone string to validate
        
    Returns:
        True if timezone is valid, False otherwise
    """
    try:
        import pytz
        pytz.timezone(timezone_str)
        return True
    except:
        try:
            # Fallback validation for basic timezone formats
            import datetime
            import zoneinfo
            zoneinfo.ZoneInfo(timezone_str)
            return True
        except:
            return False

# Create the beat schedule when module is imported
beat_schedule = create_beat_schedule()
