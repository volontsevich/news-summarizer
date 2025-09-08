"""Test text normalization and language detection."""

import pytest
from app.ingestion.normalizer import normalize_text
from app.ingestion.language import detect_language_safe


def test_normalize_text_basic():
    """Test basic text normalization."""
    text = "Hello, World! This is a TEST message with 123 numbers."
    normalized = normalize_text(text)
    
    assert normalized == "hello world this is a test message with numbers"


def test_normalize_text_special_characters():
    """Test normalization with special characters."""
    text = "Text with @mentions #hashtags & special chars!!! 🚀"
    normalized = normalize_text(text)
    
    # Should remove special characters and emojis
    assert "@" not in normalized
    assert "#" not in normalized
    assert "🚀" not in normalized
    assert "!" not in normalized


def test_normalize_text_urls():
    """Test URL removal during normalization."""
    text = "Check this out: https://example.com and also http://test.org"
    normalized = normalize_text(text)
    
    assert "https://example.com" not in normalized
    assert "http://test.org" not in normalized
    assert "check this out and also" in normalized


def test_normalize_text_empty():
    """Test normalization of empty or whitespace text."""
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""
    assert normalize_text("\n\t\r") == ""


def test_normalize_text_multiple_spaces():
    """Test normalization removes extra whitespace."""
    text = "Text    with     multiple   spaces"
    normalized = normalize_text(text)
    
    assert "text with multiple spaces" == normalized


def test_detect_language_safe_english():
    """Test language detection for English text."""
    text = "This is a sample English text for testing language detection."
    language = detect_language_safe(text)
    
    assert language == "en"


def test_detect_language_safe_short_text():
    """Test language detection with short text."""
    text = "Hi"
    language = detect_language_safe(text)
    
    # Should return 'unknown' for very short text
    assert language == "unknown"


def test_detect_language_safe_empty():
    """Test language detection with empty text."""
    assert detect_language_safe("") == "unknown"
    assert detect_language_safe("   ") == "unknown"


def test_detect_language_safe_mixed_content():
    """Test language detection with mixed content."""
    text = "Text with 123 numbers and @#$% symbols"
    language = detect_language_safe(text)
    
    # Should still detect as English despite numbers/symbols
    assert language in ["en", "unknown"]  # May be unknown due to limited real words


def test_normalize_preserves_meaning():
    """Test that normalization preserves semantic meaning."""
    original = "BREAKING: AI Company Announces Revolutionary Technology!"
    normalized = normalize_text(original)
    
    # Key words should be preserved
    assert "breaking" in normalized
    assert "ai" in normalized
    assert "company" in normalized
    assert "announces" in normalized
    assert "revolutionary" in normalized
    assert "technology" in normalized


def test_detect_language_safe_non_latin():
    """Test language detection with non-Latin text."""
    # This might return 'unknown' in simple implementations
    russian_text = "Это русский текст для тестирования"
    language = detect_language_safe(russian_text)
    
    # Should detect Russian or return unknown if not supported
    assert language in ["ru", "unknown"]
