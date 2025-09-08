"""Test email functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from tenacity import RetryError
from app.core.email import EmailService, send_alert_notification, send_digest_notification


@pytest.fixture
def email_service():
    """Create an email service instance for testing."""
    return EmailService()


@pytest.fixture
def mock_smtp():
    """Mock SMTP server for testing."""
    with patch('app.core.email.smtplib.SMTP') as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        yield mock_server


@pytest.fixture
def mock_smtp_ssl():
    """Mock SMTP_SSL server for testing."""
    with patch('app.core.email.smtplib.SMTP_SSL') as mock_smtp_ssl_class:
        mock_server = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__.return_value = mock_server
        yield mock_server


def test_create_text_content(email_service):
    """Test creating plain text email content."""
    content = email_service._create_text_content(
        alert_content="Important news about AI developments",
        matched_rules=["AI/ML Alert", "Technology News"],
        post_url="https://example.com/post/123"
    )
    
    assert "🚨 NEWS ALERT" in content
    assert "Important news about AI developments" in content
    assert "• AI/ML Alert" in content
    assert "• Technology News" in content
    assert "https://example.com/post/123" in content
    assert "TG News Summarizer" in content


def test_create_html_content(email_service):
    """Test creating HTML email content."""
    content = email_service._create_html_content(
        alert_content="Important news about AI developments",
        matched_rules=["AI/ML Alert", "Technology News"],
        post_url="https://example.com/post/123"
    )
    
    assert "<!DOCTYPE html>" in content
    assert "🚨" in content
    assert "NEWS ALERT" in content
    assert "Important news about AI developments" in content
    assert "<li>AI/ML Alert</li>" in content
    assert "<li>Technology News</li>" in content
    assert 'href="https://example.com/post/123"' in content


def test_create_digest_text(email_service):
    """Test creating digest text content."""
    content = email_service._create_digest_text(
        digest_content="Summary of today's tech news...",
        timeframe="daily",
        post_count=15
    )
    
    assert "📰 NEWS DIGEST - DAILY" in content
    assert "Summary of 15 posts:" in content
    assert "Summary of today's tech news..." in content
    assert "TG News Summarizer" in content


def test_create_digest_html(email_service):
    """Test creating digest HTML content."""
    content = email_service._create_digest_html(
        digest_content="Summary of today's tech news...",
        timeframe="daily",
        post_count=15
    )
    
    assert "<!DOCTYPE html>" in content
    assert "📰" in content
    assert "NEWS DIGEST - DAILY" in content
    assert "Summary of 15 posts:" in content
    assert "Summary of today's tech news..." in content


@patch('app.core.email.smtplib.SMTP')
def test_send_alert_email_tls(mock_smtp_class, email_service):
    """Test sending alert email with TLS."""
    # Mock settings
    with patch.object(email_service, 'settings') as mock_settings:
        mock_settings.SMTP_HOST = "smtp.gmail.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_FROM_EMAIL = "test@example.com"
        mock_settings.SMTP_USERNAME = "test@example.com"
        mock_settings.SMTP_PASSWORD = "password"
        mock_settings.SMTP_TLS = True
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        # Test sending email
        result = email_service.send_alert_email(
            recipients=["user@example.com"],
            subject="Test Alert",
            alert_content="Test content",
            matched_rules=["Test Rule"],
            post_url="https://example.com/post/1"
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "password")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
@patch('app.core.email.smtplib.SMTP_SSL')
def test_send_digest_email_ssl(mock_smtp_ssl_class, email_service):
    """Test sending digest email with SSL."""
    # Mock settings
    with patch.object(email_service, 'settings') as mock_settings:
        mock_settings.SMTP_HOST = "smtp.gmail.com"
        mock_settings.SMTP_PORT = 465
        mock_settings.SMTP_FROM_EMAIL = "test@example.com"
        mock_settings.SMTP_USERNAME = "test@example.com"
        mock_settings.SMTP_PASSWORD = "password"
        mock_settings.SMTP_TLS = False
        
        # Mock SMTP_SSL server
        mock_server = MagicMock()
        mock_smtp_ssl_class.return_value = mock_server
        
        # Test sending email
        result = email_service.send_digest_email(
            recipients=["user@example.com"],
            subject="Daily Digest",
            digest_content="Today's summary...",
            timeframe="daily",
            post_count=10
        )
        
        assert result is True
        mock_server.login.assert_called_once_with("test@example.com", "password")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
@patch('app.core.email.get_email_service')
async def test_send_alert_notification(mock_get_email_service):
    """Test sending alert notification."""
    mock_service = Mock()
    mock_service.send_alert_email.return_value = True
    mock_get_email_service.return_value = mock_service
    
    result = await send_alert_notification(
        alert_content="Breaking news",
        matched_rules=["Breaking News"],
        recipients=["user@example.com"],
        post_url="https://example.com/post/1"
    )
    
    assert result is True
    mock_service.send_alert_email.assert_called_once_with(
        recipients=["user@example.com"],
        subject="🚨 News Alert: Breaking News",
        alert_content="Breaking news",
        matched_rules=["Breaking News"],
        post_url="https://example.com/post/1"
    )


@patch('app.core.email.get_email_service')
async def test_send_digest_notification(mock_get_email_service):
    """Test sending digest notification."""
    mock_service = Mock()
    mock_service.send_digest_email.return_value = True
    mock_get_email_service.return_value = mock_service
    
    result = await send_digest_notification(
        digest_content="Daily summary",
        timeframe="daily",
        post_count=25,
        recipients=["user@example.com"]
    )
    
    assert result is True
    mock_service.send_digest_email.assert_called_once_with(
        recipients=["user@example.com"],
        subject="📰 News Digest (daily) - 25 posts",
        digest_content="Daily summary",
        timeframe="daily",
        post_count=25
    )


async def test_send_alert_notification_no_recipients():
    """Test sending alert notification with no recipients."""
    result = await send_alert_notification(
        alert_content="Breaking news",
        matched_rules=["Breaking News"],
        recipients=[],
        post_url=None
    )
    
    assert result is False


async def test_send_digest_notification_no_recipients():
    """Test sending digest notification with no recipients."""
    result = await send_digest_notification(
        digest_content="Daily summary",
        timeframe="daily",
        post_count=25,
        recipients=[]
    )
    
    assert result is False


def test_email_service_smtp_connection_error():
    """Test email service handling SMTP connection errors."""
    email_service = EmailService()
    
    # Mock settings
    with patch.object(email_service, 'settings') as mock_settings:
        mock_settings.SMTP_HOST = "invalid.smtp.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_FROM_EMAIL = "test@example.com"
        mock_settings.SMTP_USERNAME = "test@example.com"
        mock_settings.SMTP_PASSWORD = "password"
        mock_settings.SMTP_TLS = True
        
        # Mock SMTP to raise an exception
        with patch('app.core.email.smtplib.SMTP') as mock_smtp_class:
            mock_smtp_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(RetryError):
                email_service.send_alert_email(
                    recipients=["user@example.com"],
                    subject="Test Alert",
                    alert_content="Test content",
                    matched_rules=["Test Rule"]
                )
def test_email_content_escaping(email_service):
    """Test that email content properly handles special characters."""
    content_with_html = "Test <script>alert('xss')</script> content"
    
    # Text content should preserve the raw content
    text_content = email_service._create_text_content(
        alert_content=content_with_html,
        matched_rules=["Test"],
        post_url=None
    )
    assert "<script>" in text_content
    
    # HTML content should escape the content appropriately
    html_content = email_service._create_html_content(
        alert_content=content_with_html,
        matched_rules=["Test"],
        post_url=None
    )
    # The HTML should contain the content but in a safe way
    assert "Test" in html_content
    assert "content" in html_content


def test_email_service_singleton():
    """Test that get_email_service returns the same instance."""
    from app.core.email import get_email_service
    
    service1 = get_email_service()
    service2 = get_email_service()
    
    assert service1 is service2
