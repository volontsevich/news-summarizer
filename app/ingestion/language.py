# For test compatibility: safe language detection
def detect_language_safe(text: str) -> str:
    """
    Safe language detection for tests: returns 'unknown' for short/empty text, else ISO code.
    """
    if not text or len(text.strip()) < 3:
        return "unknown"
    lang = detect_lang(text)
    if not lang or lang == "en":
        # If detect_lang returns fallback 'en' for short/invalid, treat as unknown
        if len(text.strip()) < 5:
            return "unknown"
    return lang
# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Language detection and helpers."""

import logging
import re
from typing import Optional
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

logger = logging.getLogger(__name__)

def normalize_lang_code(lang_code: str) -> str:
    """
    Normalize language code to 2-letter ISO 639-1 format.
    
    Args:
        lang_code: Language code (e.g., "en", "en_US", "en-US", "eng")
        
    Returns:
        Normalized 2-letter language code (e.g., "en")
        
    Examples:
        >>> normalize_lang_code("en_US")
        'en'
        >>> normalize_lang_code("en-GB")
        'en'
        >>> normalize_lang_code("uk")
        'uk'
    """
    if not lang_code:
        return "en"  # Default fallback
    
    # Convert to lowercase and take first 2 characters
    normalized = lang_code.lower().strip()
    
    # Handle common separators (underscore, hyphen)
    if '_' in normalized or '-' in normalized:
        normalized = re.split(r'[_-]', normalized)[0]
    
    # Take first 2 characters
    normalized = normalized[:2]
    
    # Handle some common mappings
    language_mappings = {
        'ua': 'uk',  # Ukrainian sometimes detected as 'ua'
        'zh': 'zh',  # Chinese
        'ja': 'ja',  # Japanese
        'ko': 'ko',  # Korean
        'ar': 'ar',  # Arabic
        'he': 'he',  # Hebrew
        'hi': 'hi',  # Hindi
        'th': 'th',  # Thai
        'vi': 'vi',  # Vietnamese
    }
    
    return language_mappings.get(normalized, normalized)

def detect_lang(text: str) -> str:
    """
    Detect language of the given text using langdetect.
    
    Args:
        text: Text to analyze for language detection
        
    Returns:
        2-letter ISO 639-1 language code (e.g., "en", "uk", "ru")
        Returns "en" as fallback if detection fails
        
    Examples:
        >>> detect_lang("Hello world")
        'en'
        >>> detect_lang("Привет мир")
        'ru'
        >>> detect_lang("Привіт світ")
        'uk'
    """
    if not text or len(text.strip()) < 3:
        logger.debug("Text too short for language detection, defaulting to 'en'")
        return "en"
    
    try:
        # Clean text for better detection
        cleaned_text = text.strip()
        
        # Remove excessive whitespace and newlines
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # Skip if text is mostly non-alphabetic (URLs, numbers, etc.)
        alphabetic_chars = sum(1 for c in cleaned_text if c.isalpha())
        if alphabetic_chars < len(cleaned_text) * 0.3:
            logger.debug("Text contains too few alphabetic characters, defaulting to 'en'")
            return "en"
        
        # Detect language
        detected = detect(cleaned_text)
        normalized = normalize_lang_code(detected)
        
        logger.debug(f"Detected language: {detected} -> normalized: {normalized}")
        return normalized
        
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}, defaulting to 'en'")
        return "en"
    except Exception as e:
        logger.error(f"Unexpected error during language detection: {e}, defaulting to 'en'")
        return "en"

def is_supported_language(lang_code: str) -> bool:
    """
    Check if a language code is supported for processing.
    
    Args:
        lang_code: 2-letter language code
        
    Returns:
        True if language is supported, False otherwise
    """
    supported_languages = {
        'en', 'ru', 'uk', 'de', 'fr', 'es', 'it', 'pt', 'pl', 'zh', 'ja', 'ko', 'ar', 'he'
    }
    return normalize_lang_code(lang_code) in supported_languages

def get_language_name(lang_code: str) -> str:
    """
    Get human-readable language name from code.
    
    Args:
        lang_code: 2-letter language code
        
    Returns:
        Human-readable language name
    """
    language_names = {
        'en': 'English',
        'ru': 'Russian',
        'uk': 'Ukrainian',
        'de': 'German',
        'fr': 'French',
        'es': 'Spanish',
        'it': 'Italian',
        'pt': 'Portuguese',
        'pl': 'Polish',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        'ar': 'Arabic',
        'he': 'Hebrew',
    }
    normalized = normalize_lang_code(lang_code)
    return language_names.get(normalized, f"Unknown ({normalized})")
