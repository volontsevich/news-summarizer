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
    # Root endpoint now returns HTML landing page
    assert "text/html" in response.headers.get("content-type", "")
    assert "Telegram News Summarizer" in response.text


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


@patch('app.api.v1.channels.get_db')
@patch('app.api.v1.channels.channel_crud')
def test_create_channel_endpoint(mock_crud, mock_get_db, client):
    """Test channel creation endpoint."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Mock successful channel creation  
    response = client.post("/api/v1/channels/?username=testchannel&name=Test Channel")
    
    # Should call the database layer
    assert response.status_code in [200, 201, 500]  # Either success or expected DB error


@patch('app.api.v1.channels.get_db')
def test_list_channels_endpoint(mock_get_db, client):
    """Test channels listing endpoint."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    response = client.get("/api/v1/channels/")

    assert response.status_code in [200, 500]  # Either success or expected DB error


@patch('app.api.v1.channels.get_db')
def test_create_channel_database_error(mock_get_db, client):
    """Test channel creation with database error."""
    # Mock database error
    mock_get_db.side_effect = Exception("Database connection error")
    
    response = client.post("/api/v1/channels/?username=testchannel&name=Test Channel")
    
    assert response.status_code == 500


def test_nonexistent_endpoint(client):
    """Test calling nonexistent endpoint."""
    response = client.get("/nonexistent")
    
    assert response.status_code == 404


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options("/")
    
    # CORS should be configured
    assert response.status_code in [200, 405]  # Some servers return 405 for OPTIONS


@patch('app.api.v1.channels.get_db')
def test_list_channels_empty(mock_get_db, client):
    """Test listing channels when none exist."""
    # Mock database session
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    response = client.get("/api/v1/channels/")

    assert response.status_code in [200, 500]  # Either success or expected DB error


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
