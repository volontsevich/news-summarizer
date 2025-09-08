"""Text processing and normalization utilities."""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and special characters."""
    try:
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:-]', '', text)
        
        return text
    except Exception as e:
        logger.error(f"Failed to normalize text: {e}")
        return text


def detect_language_safe(text: str) -> Optional[str]:
    """Safely detect language of text."""
    try:
        # Mock implementation - would normally use langdetect or similar
        if not text or len(text.strip()) < 10:
            return None
        
        # Simple heuristic based on character patterns
        if re.search(r'[а-яё]', text.lower()):
            return 'ru'
        elif re.search(r'[a-z]', text.lower()):
            return 'en'
        else:
            return 'unknown'
    except Exception as e:
        logger.error(f"Failed to detect language: {e}")
        return None


def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """Extract keywords from text."""
    try:
        # Simple keyword extraction
        words = re.findall(r'\b\w{4,}\b', text.lower())
        # Remove common words (simple stopword removal)
        stopwords = {'this', 'that', 'with', 'have', 'will', 'from', 'they', 'been', 'were', 'said'}
        keywords = [word for word in words if word not in stopwords]
        
        # Return most frequent words
        from collections import Counter
        return [word for word, count in Counter(keywords).most_common(max_keywords)]
    except Exception as e:
        logger.error(f"Failed to extract keywords: {e}")
        return []
