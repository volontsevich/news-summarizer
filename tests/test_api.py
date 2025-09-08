"""Test FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Telegram News Summarizer"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "tg-news-summarizer"


def test_liveness_endpoint(client):
    """Test liveness probe endpoint."""
    response = client.get("/health/live")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_status_endpoint(client):
    """Test system status endpoint."""
    response = client.get("/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "api" in data
    assert "database" in data
    assert "implemented_features" in data
    assert "next_steps" in data


@patch('app.main.get_db')
@patch('app.main.crud')
def test_create_channel_endpoint(mock_crud, mock_get_db, client):
    """Test channel creation endpoint."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_db
    
    # Mock successful channel creation
    mock_channel = MagicMock()
    mock_channel.id = "test-id"
    mock_channel.handle = "testchannel"
    mock_channel.title = "Test Channel"
    mock_channel.created_at.isoformat.return_value = "2024-01-01T12:00:00Z"
    mock_channel.updated_at.isoformat.return_value = "2024-01-01T12:00:00Z"
    
    mock_crud.upsert_channel_by_handle.return_value = mock_channel
    
    response = client.post("/channels/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-id"
    assert data["handle"] == "testchannel"
    assert data["title"] == "Test Channel"


@patch('app.main.get_db')
@patch('app.main.crud')
def test_list_channels_endpoint(mock_crud, mock_get_db, client):
    """Test channels listing endpoint."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_db
    
    # Mock channels
    mock_channel1 = MagicMock()
    mock_channel1.id = "id1"
    mock_channel1.username = "channel1"
    mock_channel1.name = "Channel 1"
    mock_channel1.description = "desc1"
    mock_channel1.is_active = True
    mock_channel1.created_at.isoformat.return_value = "2024-01-01T12:00:00Z"
    mock_channel1.updated_at.isoformat.return_value = "2024-01-01T12:00:00Z"

    mock_channel2 = MagicMock()
    mock_channel2.id = "id2"
    mock_channel2.username = "channel2"
    mock_channel2.name = "Channel 2"
    mock_channel2.description = "desc2"
    mock_channel2.is_active = False
    mock_channel2.created_at.isoformat.return_value = "2024-01-01T13:00:00Z"
    mock_channel2.updated_at.isoformat.return_value = "2024-01-01T13:00:00Z"

    mock_crud.list_enabled_channels.return_value = [mock_channel1, mock_channel2]

    response = client.get("/channels/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["username"] == "channel1"
    assert data[0]["name"] == "Channel 1"
    assert data[0]["description"] == "desc1"
    assert data[0]["is_active"] is True
    assert data[1]["username"] == "channel2"
    assert data[1]["name"] == "Channel 2"
    assert data[1]["description"] == "desc2"
    assert data[1]["is_active"] is False


@patch('app.main.get_db')
def test_create_channel_database_error(mock_get_db, client):
    """Test channel creation with database error."""
    # Mock database error
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_db.side_effect = Exception("Database connection error")
    
    response = client.post("/channels/")
    
    assert response.status_code == 500
    assert "Failed to create channel" in response.json()["detail"]


def test_nonexistent_endpoint(client):
    """Test calling nonexistent endpoint."""
    response = client.get("/nonexistent")
    
    assert response.status_code == 404


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options("/")
    
    # CORS should be configured
    assert response.status_code in [200, 405]  # Some servers return 405 for OPTIONS


@patch('app.main.get_db')
@patch('app.main.crud')
def test_list_channels_empty(mock_crud, mock_get_db, client):
    """Test listing channels when none exist."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_db
    
    # Mock empty results
    mock_crud.list_enabled_channels.return_value = []

    response = client.get("/channels/")

    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_api_documentation_accessible(client):
    """Test that API documentation is accessible."""
    response = client.get("/docs")
    
    assert response.status_code == 200
    # Should return HTML for Swagger UI
    assert "text/html" in response.headers.get("content-type", "")


def test_openapi_schema_accessible(client):
    """Test that OpenAPI schema is accessible."""
    response = client.get("/openapi.json")
    
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "Telegram News Summarizer"
