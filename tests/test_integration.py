"""Integration tests for the complete system."""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


def test_telegram_client_initialization():
    """Test Telegram client can be initialized."""
    from app.telegram.client import create_telegram_client
    from app.core.config import get_settings
    
    # This will use test credentials
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.TELEGRAM_API_ID = "test_id"
        mock_settings.return_value.TELEGRAM_API_HASH = "test_hash"
        mock_settings.return_value.TELEGRAM_SESSION_NAME = "test_session"
        
        # Should not raise an exception
        client = create_telegram_client()
        assert client is not None


def test_openai_client_initialization():
    """Test OpenAI client can be initialized.""" 
    from app.llm.client import OpenAIClient
    
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.OPENAI_API_KEY = "test_key"
        mock_settings.return_value.SUMMARY_MODEL = "gpt-4o-mini"
        mock_settings.return_value.SUMMARY_MAX_TOKENS = 800
        
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
@patch('app.telegram.client.create_telegram_client')
def test_ingest_task_flow(mock_telegram, mock_db_session):
    """Test the complete ingestion task flow."""
    from app.tasks.ingest import ingest_new_posts
    
    # Mock database session
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
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


@patch('app.db.session.get_db_session')
@patch('app.utils.emailer.EmailSender')
def test_alerting_task_flow(mock_emailer, mock_db_session):
    """Test the complete alerting task flow."""
    from app.tasks.alerting import check_alert_rules
    
    # Mock database session
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    # Mock alert rules
    mock_rule = MagicMock()
    mock_rule.id = "test-rule-id"
    mock_rule.name = "AI Alert"
    mock_rule.pattern = "artificial intelligence|AI"
    mock_rule.is_active = True
    
    mock_db.scalars.return_value = [mock_rule]
    
    # Mock recent posts
    mock_post = MagicMock()
    mock_post.id = "test-post-id"
    mock_post.text = "New AI breakthrough announced"
    mock_post.normalized_text = "new ai breakthrough announced"
    mock_post.date = datetime.now(timezone.utc)
    
    # Mock the query to return posts that match
    with patch('app.tasks.alerting.crud.get_recent_unprocessed_posts') as mock_get_posts:
        mock_get_posts.return_value = [mock_post]
        
        # Mock email sender
        mock_email_instance = MagicMock()
        mock_emailer.return_value = mock_email_instance
        
        # Run the task
        result = check_alert_rules()
        
        # Should send an email
        mock_email_instance.send_alert_email.assert_called()


@patch('app.db.session.get_db_session')
@patch('app.llm.client.OpenAIClient')
@patch('app.utils.emailer.EmailSender')
def test_digest_task_flow(mock_emailer, mock_openai, mock_db_session):
    """Test the complete digest generation task flow."""
    from app.tasks.digest import generate_hourly_digest
    
    # Mock database session
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    # Mock recent posts
    mock_post1 = MagicMock()
    mock_post1.text = "AI company announces new model"
    mock_post1.date = datetime.now(timezone.utc)
    
    mock_post2 = MagicMock()
    mock_post2.text = "Tech industry updates"
    mock_post2.date = datetime.now(timezone.utc)
    
    with patch('app.tasks.digest.crud.get_last_hour_posts') as mock_get_posts:
        mock_get_posts.return_value = [mock_post1, mock_post2]
        
        # Mock OpenAI client
        mock_openai_instance = MagicMock()
        mock_openai_instance.generate_summary.return_value = "Summary of tech news"
        mock_openai.return_value = mock_openai_instance
        
        # Mock email sender
        mock_email_instance = MagicMock()
        mock_emailer.return_value = mock_email_instance
        
        # Run the task
        result = generate_hourly_digest()
        
        # Should generate summary and send email
        mock_openai_instance.generate_summary.assert_called()
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
    from app.utils.normalizer import normalize_text, detect_language_safe
    from app.utils.filters import should_filter_post
    
    # Sample text
    text = "BREAKING: AI Company Announces Revolutionary Technology! 🚀"
    
    # Normalize
    normalized = normalize_text(text)
    assert "breaking" in normalized
    assert "ai" in normalized
    
    # Detect language
    language = detect_language_safe(text)
    assert language in ["en", "unknown"]
    
    # Test filtering
    patterns = ["sports", "politics"]
    should_filter = should_filter_post(normalized, patterns)
    assert should_filter == False  # Tech news shouldn't be filtered


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
    mock_settings.return_value.OPENAI_API_KEY = None
    settings = mock_settings.return_value
    
    # Should handle missing API keys gracefully
    assert not settings.require_openai()
    
    # Test with valid settings
    mock_settings.return_value.OPENAI_API_KEY = "test_key"
    assert settings.require_openai()
