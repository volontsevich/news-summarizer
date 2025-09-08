# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Celery app and configuration."""

import logging
from celery import Celery
from app.core.config import get_settings

logger = logging.getLogger(__name__)

def create_celery_app() -> Celery:
    """
    Factory function to create and configure Celery app instance.
    
    Returns:
        Configured Celery application instance
    """
    settings = get_settings()
    
    # Create Celery app instance
    app = Celery("tg-news-summarizer")
    
    # Configure broker and result backend
    app.conf.update(
        broker_url=settings.REDIS_URL,
        result_backend=settings.REDIS_URL,
        
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        
        # Timezone settings
        timezone=settings.TIMEZONE,
        enable_utc=True,
        
        # Task discovery
        include=[
            "app.tasks.ingest",
            "app.tasks.alerting", 
            "app.tasks.digest",
            "app.tasks.celery_app",  # Include this module for ping task
        ],
        
        # Task routing and execution
        task_routes={
            'app.tasks.ingest.*': {'queue': 'ingest'},
            'app.tasks.alerting.*': {'queue': 'alerts'},
            'app.tasks.digest.*': {'queue': 'digest'},
        },
        
        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        
        # Result settings
        result_expires=3600,  # 1 hour
        
        # Error handling
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
    )
    
    # Import beat schedule if available
    try:
        from app.tasks.schedules import beat_schedule
        app.conf.beat_schedule = beat_schedule
        logger.info("Loaded beat schedule from app.tasks.schedules")
    except ImportError:
        logger.warning("No beat schedule found in app.tasks.schedules")
    
    logger.info(f"Celery app configured with broker: {settings.REDIS_URL}")
    return app

# Create the global Celery app instance
celery = create_celery_app()

@celery.task(name="ping")
def ping() -> dict:
    """
    Health check task for monitoring Celery worker status.
    
    Returns:
        Dict with status information
    """
    import datetime
    
    return {
        "status": "ok",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "worker": "celery",
        "message": "pong"
    }

@celery.task(name="health_check")
def health_check() -> dict:
    """
    Comprehensive health check task that verifies various system components.
    
    Returns:
        Dict with detailed health status
    """
    import datetime
    from app.core.config import get_settings
    
    settings = get_settings()
    health_status = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "celery": "ok",
        "redis": "unknown",
        "database": "unknown",
        "overall": "ok"
    }
    
    try:
        # Test Redis connection
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health_status["redis"] = "ok"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["overall"] = "degraded"
    
    try:
        # Test database connection (basic check)
        from app.db.session import get_db
        # Note: This is a simple test, in practice you'd want to test actual DB connectivity
        health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["overall"] = "degraded"
    
    return health_status

# Autodiscover tasks in app.tasks modules
celery.autodiscover_tasks(['app.tasks'])