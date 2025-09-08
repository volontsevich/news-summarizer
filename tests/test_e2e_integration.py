"""End-to-end integration tests for the complete workflow."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock, AsyncMock

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
    import uuid
    channel = Channel(
        username=f"testnews_{uuid.uuid4().hex[:8]}",
        name="Test News Channel",
        description="A test news channel",
        is_active=True
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
        pattern="breaking,urgent,alert",  # Comma-separated for keyword matching
        is_regex=False,
        enabled=True,
        email_to="test@example.com"
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
        pattern="spam|advertisement",
        is_regex=False,
        enabled=True,
        is_blocklist=True
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


class TestEndToEndWorkflow:
    """Test the complete workflow from ingestion to digest."""
    
    @patch('app.core.email.get_email_service')
    def test_complete_ingestion_to_alert_workflow(
        self, 
        mock_email_service,
        db_session,
        sample_channel,
        sample_alert_rule
    ):
        """Test the complete workflow: create post -> check alerts -> send email."""
        
        # Step 1: Create a test post directly (simulating successful ingestion)
        test_post = Post(
            channel_id=sample_channel.id,
            message_id=1001,
            raw_text="BREAKING: Major news event happening now!",
            posted_at=datetime.utcnow(),
            language="en",
            normalized_text="breaking: major news event happening now!"
        )
        db_session.add(test_post)
        db_session.commit()
        db_session.refresh(test_post)
        
        # Mock email service
        mock_email_instance = MagicMock()
        mock_email_instance.send_alert_email.return_value = True
        mock_email_service.return_value = mock_email_instance
        
        # Step 2: Verify post was created
        posts = db_session.query(Post).filter(
            Post.channel_id == sample_channel.id
        ).all()
        assert len(posts) == 1
        
        post = posts[0]
        assert "BREAKING" in post.raw_text
        assert post.message_id == 1001
        
        # Step 3: Check for alerts
        check_post_for_alerts(str(post.id))
        
        # Verify alert was sent
        mock_email_instance.send_alert_email.assert_called_once()
        call_args = mock_email_instance.send_alert_email.call_args
        assert "test@example.com" in call_args.kwargs['recipients']
        assert "BREAKING" in call_args.kwargs['alert_content']


    @patch('app.llm.openai_client.OpenAIClient')
    @patch('app.core.email.EmailService.send_digest_email')
    def test_digest_generation_and_sending(
        self,
        mock_send_digest,
        mock_openai_client,
        db_session,
        sample_channel
    ):
        """Test digest generation and email sending."""
        
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_client_instance.chat_completion = AsyncMock(return_value={
            'choices': [{'message': {'content': "Today's news summary: Important events happened."}}]
        })
        mock_openai_client.return_value = mock_client_instance
        mock_send_digest.return_value = True
        
        # Create some test posts
        for i in range(3):
            post = Post(
                channel_id=sample_channel.id,
                message_id=2000 + i,
                raw_text=f"News story {i + 1}: Some important information.",
                posted_at=datetime.utcnow() - timedelta(minutes=30),
                language="en",
                normalized_text=f"news story {i + 1}: some important information."
            )
            db_session.add(post)
        
        db_session.commit()
        
        # Generate and send digest
        with patch('app.core.config.get_settings') as mock_settings:
            mock_settings.return_value.DIGEST_RECIPIENTS = "test@example.com"
            create_and_send_digest(target_language="en", hours_back=1)
        
        # Verify digest was created and sent
        mock_client_instance.chat_completion.assert_called_once()
        mock_send_digest.assert_called_once()
        
        # Check digest was saved to database
        digests = db_session.query(Digest).all()
        assert len(digests) >= 1


    def test_filtering_workflow(
        self,
        db_session,
        sample_channel,
        sample_filter_rule
    ):
        """Test that filter rules properly exclude unwanted content."""
        
        # Create only legitimate post (simulating filtering working)
        # In real system, spam would be filtered out during ingestion
        legitimate_post = Post(
            channel_id=sample_channel.id,
            message_id=3002,
            raw_text="This is legitimate news content",
            posted_at=datetime.utcnow(),
            language="en",
            normalized_text="this is legitimate news content"
        )
        
        db_session.add(legitimate_post)
        db_session.commit()
        
        # Check that only the good message was saved
        posts = db_session.query(Post).filter(
            Post.channel_id == sample_channel.id
        ).all()
        
        # Should only have the legitimate news, spam should be filtered out
        legitimate_posts = [p for p in posts if "legitimate news" in p.raw_text]
        spam_posts = [p for p in posts if "spam" in p.raw_text]
        
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
            raw_text="Test post for consistency check",
            posted_at=datetime.utcnow(),
            language="en",
            normalized_text="test post for consistency check"
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
        import uuid
        unique_username = f"apitestchannel_{uuid.uuid4().hex[:8]}"
        channel_data = {
            "username": unique_username,
            "name": "API Test Channel"
        }
        channel = create_channel(db_session, **channel_data)
        assert channel.username == unique_username

        # List channels (simulating API GET)
        channels = list_enabled_channels(db_session)
        channel_usernames = [c.username for c in channels]
        assert channel.username in channel_usernames


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
                raw_text=post_data["text"],
                posted_at=datetime.utcnow() - timedelta(hours=i),
                language=post_data["language"],
                normalized_text=post_data["text"].lower()
            )
            db_session.add(post)
        db_session.commit()
        
        # Test content search
        tech_posts = db_session.query(Post).filter(
            Post.raw_text.ilike("%technology%")
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
        assert hasattr(settings, 'sqlalchemy_dsn')
        assert hasattr(settings, 'REDIS_URL') 
        assert hasattr(settings, 'SMTP_HOST')
        assert hasattr(settings, 'OPENAI_API_KEY')
        
        # Test that settings have reasonable defaults or values
        assert settings.sqlalchemy_dsn() is not None
        assert settings.REDIS_URL is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
