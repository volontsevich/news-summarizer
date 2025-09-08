"""Test configuration and fixtures."""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Channel, Post, FilterRule, AlertRule
from app.core.config import get_settings


@pytest.fixture
def test_db():
    """Create a test database session using PostgreSQL."""
    # Use PostgreSQL from docker-compose for testing
    database_url = "postgresql://postgres:postgres@db:5432/tgnews"
    
    engine = create_engine(database_url, echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Clean up tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_channel(test_db):
    """Create a sample channel for testing."""
    channel = Channel(
        username="testchannel",
        name="Test Channel",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(channel)
    test_db.commit()
    test_db.refresh(channel)
    return channel


@pytest.fixture
def sample_post(test_db, sample_channel):
    """Create a sample post for testing."""
    post = Post(
        channel_id=sample_channel.id,
        message_id=12345,
        raw_text="This is a test message about technology news.",
        posted_at=datetime.now(timezone.utc),
        language="en",
        normalized_text="this is a test message about technology news"
    )
    test_db.add(post)
    test_db.commit()
    test_db.refresh(post)
    return post


@pytest.fixture
def sample_filter_rule(test_db):
    """Create a sample filter rule for testing."""
    rule = FilterRule(
        name="Block Sports",
        pattern="sports|football|basketball",
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(rule)
    test_db.commit()
    test_db.refresh(rule)
    return rule


@pytest.fixture
def sample_alert_rule(test_db):
    """Create a sample alert rule for testing."""
    rule = AlertRule(
        name="AI/ML Alert",
        pattern="artificial intelligence|machine learning|AI|ML",
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(rule)
    test_db.commit()
    test_db.refresh(rule)
    return rule


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    class MockSettings:
        TELEGRAM_API_ID = "test_api_id"
        TELEGRAM_API_HASH = "test_api_hash"
        TELEGRAM_SESSION_NAME = "test_session"
        OPENAI_API_KEY = "test_openai_key"
        SUMMARY_TARGET_LANG = "en"
        SUMMARY_MODEL = "gpt-4o-mini"
        SMTP_HOST = "test.smtp.com"
        SMTP_PORT = 587
        SMTP_USERNAME = "test@example.com"
        SMTP_PASSWORD = "test_password"
        SMTP_TLS = True
        DEBUG = True
        
        def sqlalchemy_dsn(self):
            return "sqlite:///:memory:"
    
    return MockSettings()
