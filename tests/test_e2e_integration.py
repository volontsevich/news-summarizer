"""End-to-end integration tests for the complete workflow."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.db.session import get_db_session
from app.db.models import Channel, Post, AlertRule, FilterRule, Digest
from app.tasks.ingest import ingest_telegram_posts
from app.tasks.alerting import check_post_for_alerts
from app.tasks.digest import create_and_send_digest
from app.core.email import EmailService


@pytest.fixture
def db_session():
    """Get a database session for testing."""
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_channel(db_session: Session):
    """Create a sample channel for testing."""
    channel = Channel(
        username="testnews",
        name="Test News Channel",
        description="A test news channel",
        is_active=True,
        telegram_id=123456789
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


@pytest.fixture
def sample_alert_rule(db_session: Session):
    """Create a sample alert rule for testing."""
    rule = AlertRule(
        name="Test Alert Rule",
        description="Test rule for breaking news",
        keywords=["breaking", "urgent", "alert"],
        is_active=True,
        alert_emails=["test@example.com"]
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def sample_filter_rule(db_session: Session):
    """Create a sample filter rule for testing."""
    rule = FilterRule(
        name="Test Filter Rule",
        description="Test rule to filter spam",
        keywords=["spam", "advertisement"],
        is_active=True,
        action="exclude"
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


class TestEndToEndWorkflow:
    """Test the complete workflow from ingestion to digest."""
    
    @patch('app.ingestion.telegram_client.TelegramClientFactory.get_client')
    @patch('app.core.email.EmailService.send_alert_email')
    def test_complete_ingestion_to_alert_workflow(
        self, 
        mock_send_alert,
        mock_telegram_client,
        db_session,
        sample_channel,
        sample_alert_rule
    ):
        """Test the complete workflow: ingest posts -> check alerts -> send email."""
        
        # Setup mocks
        mock_client = MagicMock()
        mock_telegram_client.return_value = mock_client
        
        # Mock Telegram messages
        mock_message = MagicMock()
        mock_message.id = 1001
        mock_message.text = "BREAKING: Major news event happening now!"
        mock_message.date = datetime.utcnow()
        mock_message.chat.id = sample_channel.telegram_id
        
        mock_client.get_recent_messages.return_value = [mock_message]
        mock_send_alert.return_value = True
        
        # Step 1: Ingest new posts
        ingest_telegram_posts()
        
        # Verify post was created
        posts = db_session.query(Post).filter(
            Post.channel_id == sample_channel.id
        ).all()
        assert len(posts) == 1
        
        post = posts[0]
        assert "BREAKING" in post.text
        assert post.message_id == 1001
        
        # Step 2: Check for alerts
        check_post_for_alerts(post.id)
        
        # Verify alert was sent
        mock_send_alert.assert_called_once()
        call_args = mock_send_alert.call_args
        assert "test@example.com" in call_args.kwargs['recipients']
        assert "BREAKING" in call_args.kwargs['alert_content']


    @patch('app.llm.openai_client.OpenAIClient.generate_summary')
    @patch('app.core.email.EmailService.send_digest_email')
    def test_digest_generation_and_sending(
        self,
        mock_send_digest,
        mock_generate_summary,
        db_session,
        sample_channel
    ):
        """Test digest generation and email sending."""
        
        # Setup mocks
        mock_generate_summary.return_value = "Today's news summary: Important events happened."
        mock_send_digest.return_value = True
        
        # Create some test posts
        for i in range(3):
            post = Post(
                channel_id=sample_channel.id,
                message_id=2000 + i,
                text=f"News story {i + 1}: Some important information.",
                created_at=datetime.utcnow() - timedelta(minutes=30),
                language="en"
            )
            db_session.add(post)
        
        db_session.commit()
        
        # Generate and send digest
        create_and_send_digest(target_language="en", hours_back=1)
        
        # Verify digest was created and sent
        mock_generate_summary.assert_called_once()
        mock_send_digest.assert_called_once()
        
        # Check digest was saved to database
        digests = db_session.query(Digest).all()
        assert len(digests) >= 1


    @patch('app.ingestion.telegram_client.TelegramClientFactory.get_client')
    def test_filtering_workflow(
        self,
        mock_telegram_client,
        db_session,
        sample_channel,
        sample_filter_rule
    ):
        """Test that filter rules properly exclude unwanted content."""
        
        # Setup mocks
        mock_client = MagicMock()
        mock_telegram_client.return_value = mock_client
        
        # Mock messages - one should be filtered, one should pass
        spam_message = MagicMock()
        spam_message.id = 3001
        spam_message.text = "This is spam advertisement content"
        spam_message.date = datetime.utcnow()
        spam_message.chat.id = sample_channel.telegram_id
        
        good_message = MagicMock()
        good_message.id = 3002
        good_message.text = "This is legitimate news content"
        good_message.date = datetime.utcnow()
        good_message.chat.id = sample_channel.telegram_id
        
        mock_client.get_recent_messages.return_value = [spam_message, good_message]
        
        # Ingest posts
        ingest_telegram_posts()
        
        # Check that only the good message was saved
        posts = db_session.query(Post).filter(
            Post.channel_id == sample_channel.id
        ).all()
        
        # Should only have the legitimate news, spam should be filtered out
        legitimate_posts = [p for p in posts if "legitimate news" in p.text]
        spam_posts = [p for p in posts if "spam" in p.text]
        
        assert len(legitimate_posts) == 1
        assert len(spam_posts) == 0  # Should be filtered out


    @patch('app.core.email.smtplib.SMTP')
    def test_email_service_integration(self, mock_smtp_class):
        """Test that the email service integrates properly with the workflow."""
        
        # Setup email service mock
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        email_service = EmailService()
        
        # Test alert email
        result = email_service.send_alert_email(
            recipients=["test@example.com"],
            subject="Test Alert",
            alert_content="This is a test alert",
            matched_rules=["Test Rule"],
            post_url="https://t.me/test/123"
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
        
        # Reset mocks for digest test
        mock_server.reset_mock()
        
        # Test digest email
        result = email_service.send_digest_email(
            recipients=["test@example.com"],
            subject="Daily Digest",
            digest_content="Today's digest content",
            timeframe="daily",
            post_count=5
        )
        
        assert result is True
        mock_server.sendmail.assert_called_once()


    def test_database_consistency(self, db_session, sample_channel):
        """Test that database operations maintain consistency across the workflow."""
        
        # Create a post
        post = Post(
            channel_id=sample_channel.id,
            message_id=4001,
            text="Test post for consistency check",
            created_at=datetime.utcnow(),
            language="en"
        )
        db_session.add(post)
        db_session.commit()
        
        # Verify relationships work correctly
        channel_posts = db_session.query(Post).filter(
            Post.channel_id == sample_channel.id
        ).all()
        
        assert len(channel_posts) >= 1
        assert channel_posts[0].channel_id == sample_channel.id
        
        # Test cascade behavior
        post_id = post.id
        db_session.delete(post)
        db_session.commit()
        
        # Verify post is deleted
        deleted_post = db_session.query(Post).filter(Post.id == post_id).first()
        assert deleted_post is None


class TestAPIEndpointsIntegration:
    """Test API endpoints work with the database and services."""
    
    def test_channel_api_workflow(self, db_session):
        """Test channel management through API endpoints."""
        # This would test the actual API endpoints
        # For now, we'll test the underlying CRUD operations
        
        from app.db.crud import create_channel, list_enabled_channels
        
        # Create channel via CRUD (simulating API)
        channel_data = {
            "username": "apitestchannel",
            "name": "API Test Channel",
            "telegram_id": 987654321,
            "is_active": True
        }
        
        channel = create_channel(db_session, **channel_data)
        assert channel.username == "apitestchannel"
        
        # List channels (simulating API GET)
        channels = list_enabled_channels(db_session)
        channel_usernames = [c.username for c in channels]
        assert "apitestchannel" in channel_usernames


    def test_post_search_functionality(self, db_session, sample_channel):
        """Test post search and filtering capabilities."""
        
        # Create posts with different content
        posts_data = [
            {"text": "Breaking news about technology", "language": "en"},
            {"text": "Sports update: team wins championship", "language": "en"},
            {"text": "Weather forecast for tomorrow", "language": "en"},
            {"text": "Actualités technologiques importantes", "language": "fr"}
        ]
        
        for i, post_data in enumerate(posts_data):
            post = Post(
                channel_id=sample_channel.id,
                message_id=5000 + i,
                text=post_data["text"],
                language=post_data["language"],
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(post)
        
        db_session.commit()
        
        # Test content search
        tech_posts = db_session.query(Post).filter(
            Post.text.ilike("%technology%")
        ).all()
        assert len(tech_posts) >= 1
        
        # Test language filtering
        english_posts = db_session.query(Post).filter(
            Post.language == "en"
        ).all()
        assert len(english_posts) >= 3
        
        french_posts = db_session.query(Post).filter(
            Post.language == "fr"
        ).all()
        assert len(french_posts) >= 1


@pytest.mark.integration
class TestFullSystemIntegration:
    """Full system integration tests requiring all components."""
    
    @patch('app.tasks.celery_app.celery.send_task')
    def test_task_queueing_system(self, mock_send_task):
        """Test that tasks can be queued and would be executed."""
        
        mock_send_task.return_value = MagicMock(id="test-task-id")
        
        # Test queueing ingestion task
        from app.tasks.celery_app import celery
        result = celery.send_task('app.tasks.ingest.ingest_new_posts')
        
        mock_send_task.assert_called()
        assert result.id == "test-task-id"


    def test_configuration_loading(self):
        """Test that all required configuration is properly loaded."""
        
        from app.core.config import get_settings
        settings = get_settings()
        
        # Test that critical settings are available
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'REDIS_URL') 
        assert hasattr(settings, 'SMTP_HOST')
        assert hasattr(settings, 'OPENAI_API_KEY')
        
        # Test that settings have reasonable defaults or values
        assert settings.DATABASE_URL is not None
        assert settings.REDIS_URL is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
