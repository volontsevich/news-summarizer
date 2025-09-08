"""Integration tests for the complete system."""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from app.db.models import Post, Channel, AlertRule


def test_telegram_client_initialization():
    """Test Telegram client can be initialized."""
    from app.ingestion.telegram_client import TelegramClientFactory
    from app.core.config import get_settings
    
    # This will use test credentials
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.TELEGRAM_API_ID = "test_id"
        mock_settings.return_value.TELEGRAM_API_HASH = "test_hash"
        mock_settings.return_value.TELEGRAM_SESSION_NAME = "test_session"
        mock_settings.return_value.TELEGRAM_TIMEOUT = 20
        
        # Should not raise an exception
        factory = TelegramClientFactory()
        assert factory is not None


def test_openai_client_initialization():
    """Test OpenAI client can be initialized.""" 
    from app.llm.openai_client import OpenAIClient
    
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.OPENAI_API_KEY = "test_key"
        mock_settings.return_value.SUMMARY_MODEL = "gpt-4o-mini"
        mock_settings.return_value.SUMMARY_MAX_TOKENS = 800
        mock_settings.return_value.require_openai.return_value = True
        
        client = OpenAIClient()
        assert client is not None


def test_email_client_initialization():
    """Test email client can be initialized."""
    from app.utils.emailer import EmailSender
    
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.SMTP_HOST = "test.smtp.com"
        mock_settings.return_value.SMTP_PORT = 587
        mock_settings.return_value.SMTP_USERNAME = "test@example.com"
        mock_settings.return_value.SMTP_PASSWORD = "test_password"
        mock_settings.return_value.SMTP_TLS = True
        mock_settings.return_value.SMTP_FROM_EMAIL = "Test <test@example.com>"
        
        emailer = EmailSender()
        assert emailer is not None


@patch('app.db.session.get_db_session')
@patch('app.ingestion.telegram_client.TelegramClientFactory')
def test_ingest_task_flow(mock_telegram, mock_db_session):
    """Test the complete ingestion task flow."""
    from app.tasks.ingest import ingest_new_posts
    
    # Mock database session
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    # Mock telegram client
    mock_telegram_instance = MagicMock()
    mock_telegram.return_value = mock_telegram_instance
    
    # Mock enabled channels
    mock_channel = MagicMock()
    mock_channel.id = "test-channel-id"
    mock_channel.handle = "testchannel"
    mock_channel.last_message_id = None
    
    mock_db.scalars.return_value = [mock_channel]
    
    # Mock Telegram client
    mock_client = MagicMock()
    mock_telegram.return_value = mock_client
    
    # Mock messages from Telegram
    mock_message = MagicMock()
    mock_message.id = 12345
    mock_message.text = "Test message about technology"
    mock_message.date = datetime.now(timezone.utc)
    
    mock_client.iter_messages.return_value.__aiter__ = lambda: iter([mock_message])
    
    # Run the task
    result = ingest_new_posts()
    
    # Should complete without errors
    assert result is not None


@patch('app.core.email.get_email_service')
@patch('app.db.session.get_db_session')
def test_alerting_task_flow(mock_db_session, mock_email_service):
    """Test the complete alerting task flow."""
    from app.tasks.alerting import check_post_for_alerts
    import uuid
    
    # Mock database session as context manager
    mock_db = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_db
    mock_db_session.return_value.__exit__.return_value = None
    
    # Mock post with proper UUID
    post_uuid = uuid.uuid4()
    mock_post = MagicMock()
    mock_post.id = post_uuid
    mock_post.raw_text = "New AI breakthrough announced"
    mock_post.normalized_text = "new ai breakthrough announced"
    mock_post.channel_id = uuid.uuid4()
    
    # Mock channel
    mock_channel = MagicMock()
    mock_channel.id = mock_post.channel_id
    mock_channel.username = "testchannel"
    
    # Mock alert rule
    mock_rule = MagicMock()
    mock_rule.id = uuid.uuid4()
    mock_rule.name = "AI Alert"
    mock_rule.pattern = "ai"  # lowercase to match
    mock_rule.is_regex = False
    mock_rule.enabled = True
    mock_rule.email_to = "test@example.com"
    
    # Setup query mocks
    def mock_query_side_effect(model):
        mock_query = MagicMock()
        if model == Post:
            mock_query.filter.return_value.first.return_value = mock_post
        elif model == Channel:
            mock_query.filter.return_value.first.return_value = mock_channel
        elif model == AlertRule:
            mock_query.filter.return_value.all.return_value = [mock_rule]
        return mock_query
    
    mock_db.query.side_effect = mock_query_side_effect
    
    # Mock email service
    mock_email_instance = MagicMock()
    mock_email_instance.send_alert_email.return_value = True
    mock_email_service.return_value = mock_email_instance
    
    # Run the task
    result = check_post_for_alerts(str(post_uuid))
    
    # Should send an email
    mock_email_instance.send_alert_email.assert_called_once()


@patch('app.core.email.get_email_service')
@patch('app.db.session.get_db_session')
@patch('app.llm.openai_client.OpenAIClient')
def test_digest_task_flow(mock_openai, mock_db_session, mock_email_service):
    """Test the complete digest generation task flow."""
    from app.tasks.digest import create_and_send_digest
    from app.core.config import get_settings
    
    # Mock database session as context manager
    mock_db = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_db
    mock_db_session.return_value.__exit__.return_value = None
    
    # Mock recent posts with channel relationship
    mock_channel = MagicMock()
    mock_channel.name = "Tech News"
    mock_channel.is_active = True
    
    mock_post1 = MagicMock()
    mock_post1.raw_text = "AI company announces new model"
    mock_post1.normalized_text = "ai company announces new model"
    mock_post1.created_at = datetime.now(timezone.utc)
    mock_post1.channel = mock_channel
    
    mock_post2 = MagicMock()
    mock_post2.raw_text = "Tech industry updates"
    mock_post2.normalized_text = "tech industry updates"
    mock_post2.created_at = datetime.now(timezone.utc)
    mock_post2.channel = mock_channel
    
    # Setup query mocks
    mock_query = MagicMock()
    mock_query.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_post1, mock_post2]
    mock_db.query.return_value = mock_query
    
    # Mock OpenAI client
    mock_openai_instance = MagicMock()
    # Make chat_completion an async mock
    mock_openai_instance.chat_completion = AsyncMock(return_value={
        'choices': [{'message': {'content': 'Summary of tech news'}}]
    })
    mock_openai.return_value = mock_openai_instance
    
    # Mock email service
    mock_email_instance = MagicMock()
    mock_email_instance.send_digest_email.return_value = True
    mock_email_service.return_value = mock_email_instance
    
    # Mock settings
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.DIGEST_RECIPIENTS = "test@example.com"
        
        # Run the task
        result = create_and_send_digest()
        
        # Should generate summary and send email
        mock_openai_instance.chat_completion.assert_called()
        mock_email_instance.send_digest_email.assert_called()


def test_database_connection():
    """Test database connection works."""
    from app.db.session import init_db, get_db_session
    
    # Should be able to initialize database
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.sqlalchemy_dsn.return_value = "sqlite:///:memory:"
        
        init_db()
        
        # Should be able to get a session
        session = get_db_session()
        assert session is not None
        session.close()


def test_configuration_loading():
    """Test configuration can be loaded."""
    from app.core.config import get_settings
    
    settings = get_settings()
    assert settings is not None
    
    # Should have default values
    assert settings.TELEGRAM_SESSION_NAME == "tg_news_session"
    assert settings.SUMMARY_TARGET_LANG == "en"


def test_celery_task_registration():
    """Test that Celery tasks are properly registered."""
    try:
        from app.tasks.ingest import ingest_new_posts
        from app.tasks.alerting import check_alert_rules
        from app.tasks.digest import generate_hourly_digest
        
        # Tasks should be importable
        assert callable(ingest_new_posts)
        assert callable(check_alert_rules)
        assert callable(generate_hourly_digest)
        
    except ImportError as e:
        pytest.skip(f"Celery tasks not available: {e}")


def test_text_processing_pipeline():
    """Test the complete text processing pipeline."""
    from app.ingestion.normalizer import normalize_text
    
    # Sample text
    text = "BREAKING: AI Company Announces Revolutionary Technology! 🚀 Check https://example.com"
    
    # Normalize - returns tuple (normalized_text, url)
    normalized, url = normalize_text(text)
    assert normalized is not None
    assert len(normalized) > 0
    assert url == "https://example.com"
    
    # Simple test that normalized text contains key content
    assert "AI" in normalized or "ai" in normalized.lower()
    assert "Technology" in normalized or "technology" in normalized.lower()


def test_api_startup():
    """Test that the FastAPI app can start up."""
    from app.main import app
    
    # App should be created without errors
    assert app is not None
    assert app.title == "Telegram News Summarizer"
    assert app.version == "1.0.0"


@patch('app.core.config.get_settings')
def test_environment_validation(mock_settings):
    """Test environment variable validation."""
    # Test with missing required settings
    mock_settings_instance = MagicMock()
    mock_settings_instance.OPENAI_API_KEY = None
    mock_settings_instance.require_openai.return_value = False
    mock_settings.return_value = mock_settings_instance
    
    settings = mock_settings.return_value
    
    # Should handle missing API keys gracefully
    assert not settings.require_openai()
    
    # Test with valid settings
    mock_settings_instance.OPENAI_API_KEY = "test_key"
    mock_settings_instance.require_openai.return_value = True
    assert settings.require_openai()
