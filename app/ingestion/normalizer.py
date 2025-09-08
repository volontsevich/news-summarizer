# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Text normalization utilities."""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Regex patterns for text normalization
URL_PATTERN = re.compile(
    r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
    re.IGNORECASE
)

# Emoji pattern - matches most Unicode emoji ranges
EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F'  # emoticons
    r'\U0001F300-\U0001F5FF'   # symbols & pictographs
    r'\U0001F680-\U0001F6FF'   # transport & map symbols
    r'\U0001F1E0-\U0001F1FF'   # flags (iOS)
    r'\U00002700-\U000027BF'   # dingbats
    r'\U0001F900-\U0001F9FF'   # supplemental symbols and pictographs
    r'\U00002600-\U000026FF'   # miscellaneous symbols
    r'\U0001F200-\U0001F2FF'   # enclosed characters
    r']+',
    re.UNICODE
)

def normalize_text(text: str) -> Tuple[str, Optional[str]]:
    """
    Normalize text by collapsing whitespace, optionally stripping emojis,
    and extracting the first URL.
    
    Args:
        text: Raw text to normalize
        
    Returns:
        Tuple of (normalized_text, first_url_found)
        
    Examples:
        >>> normalize_text("Hello   world! 😀 Check https://example.com")
        ('Hello world! Check', 'https://example.com')
        >>> normalize_text("   Multiple    spaces   ")
        ('Multiple spaces', None)
        >>> normalize_text("")
        ('', None)
    """
    if not text:
        return ("", None)
    
    try:
        # Extract URLs first (before text modification)
        urls = URL_PATTERN.findall(text)
        main_url = urls[0] if urls else None
        
        # Start with the original text
        normalized = text
        
        # Remove URLs from the text to avoid them cluttering the content
        normalized = URL_PATTERN.sub('', normalized)
        
        # Remove emojis (optional - can be configured)
        # For now, keep them as they might contain meaningful context
        # normalized = EMOJI_PATTERN.sub('', normalized)
        
        # Collapse multiple whitespace characters into single spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading and trailing whitespace
        normalized = normalized.strip()
        
        # Remove excessive punctuation repetition (e.g., "!!!" -> "!")
        normalized = re.sub(r'([.!?]){3,}', r'\1', normalized)
        
        # Clean up common Telegram formatting artifacts
        # Remove zero-width characters and other invisible characters
        normalized = re.sub(r'[\u200b-\u200f\ufeff]', '', normalized)
        
        # Remove excessive newlines that might have been converted to spaces
        normalized = re.sub(r'\s*\n\s*', ' ', normalized)
        
        logger.debug(f"Normalized text: '{text[:50]}...' -> '{normalized[:50]}...', URL: {main_url}")
        
        return (normalized, main_url)
        
    except Exception as e:
        logger.error(f"Error normalizing text: {e}")
        # Return safe fallback
        return (text.strip() if text else "", None)

def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs from text.
    
    Args:
        text: Text to search for URLs
        
    Returns:
        List of URLs found in the text
    """
    if not text:
        return []
    
    try:
        return URL_PATTERN.findall(text)
    except Exception as e:
        logger.error(f"Error extracting URLs: {e}")
        return []

def strip_emojis(text: str) -> str:
    """
    Remove emojis from text.
    
    Args:
        text: Text to clean
        
    Returns:
        Text with emojis removed
    """
    if not text:
        return ""
    
    try:
        return EMOJI_PATTERN.sub('', text).strip()
    except Exception as e:
        logger.error(f"Error stripping emojis: {e}")
        return text

def clean_whitespace(text: str) -> str:
    """
    Collapse and normalize whitespace in text.
    
    Args:
        text: Text to clean
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    try:
        # Replace multiple whitespace with single space
        cleaned = re.sub(r'\s+', ' ', text)
        return cleaned.strip()
    except Exception as e:
        logger.error(f"Error cleaning whitespace: {e}")
        return text.strip()

def is_meaningful_text(text: str, min_length: int = 10) -> bool:
    """
    Check if text contains meaningful content (not just URLs, emojis, etc.).
    
    Args:
        text: Text to evaluate
        min_length: Minimum length for meaningful text
        
    Returns:
        True if text appears to contain meaningful content
    """
    if not text or len(text.strip()) < min_length:
        return False
    
    try:
        # Remove URLs and emojis to check actual text content
        cleaned = URL_PATTERN.sub('', text)
        cleaned = EMOJI_PATTERN.sub('', cleaned)
        cleaned = clean_whitespace(cleaned)
        
        # Check if we have enough alphabetic characters
        alphabetic_chars = sum(1 for c in cleaned if c.isalpha())
        return alphabetic_chars >= min_length * 0.5
        
    except Exception as e:
        logger.error(f"Error checking text meaningfulness: {e}")
        return len(text.strip()) >= min_length
