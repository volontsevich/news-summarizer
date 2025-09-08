# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Prompt templates for LLM tasks."""

from typing import List, Dict, Any
from datetime import datetime

def get_summary_prompt(posts: List[Dict[str, Any]], target_lang: str = "en") -> str:
    """
    Generate summary prompt for multilingual Telegram posts.
    
    Args:
        posts: List of posts with keys: channel_handle, text, url, posted_at
        target_lang: Target language for the summary (e.g., "en", "uk", "ru")
        
    Returns:
        Formatted prompt for LLM summarization
    """
    # Format posts for the prompt
    formatted_posts = []
    for i, post in enumerate(posts, 1):
        # Support both 'channel_handle' and 'channel' for compatibility
        channel = post.get('channel_handle') or post.get('channel', 'unknown')
        text = post.get('text', '')
        url = post.get('url', '')
        timestamp = post.get('posted_at') or post.get('date', '')
        
        post_entry = f"Post {i}:\n"
        post_entry += f"Channel: {channel}\n"
        post_entry += f"Time: {timestamp}\n"
        post_entry += f"Text: {text}\n"
        if url:
            post_entry += f"Link: {url}\n"
        formatted_posts.append(post_entry)
    
    posts_text = "\n---\n".join(formatted_posts)
    
    # Language-specific instructions
    lang_instructions = {
        "en": "English",
        "uk": "Ukrainian", 
        "ru": "Russian",
        "de": "German",
        "fr": "French",
        "es": "Spanish"
    }
    target_language = lang_instructions.get(target_lang, "English")
    
    return f"""You are a professional news analyst. Analyze the following Telegram posts and create a comprehensive digest in {target_language}.

INPUT DATA:
{posts_text}

INSTRUCTIONS:
1. Create a clear, informative headline
2. Group similar topics together and create 5-10 bullet points
3. Each bullet should cite the source channel and include the link when available
4. Add a brief "What Changed" section highlighting key developments
5. De-duplicate near-identical information from multiple sources
6. Use neutral, analytical tone - remove sensationalism and emotional language
7. If the content is low-signal or lacks substantial news value, state this briefly

OUTPUT FORMAT:
# [Headline]

## Key Developments
• [Topic 1]: [Summary] (Source: @channel_name - [link if available])
• [Topic 2]: [Summary] (Source: @channel_name - [link if available])
[... 5-10 bullets total ...]

## What Changed
[Brief summary of key developments and trends]

IMPORTANT:

Begin your analysis:"""

def get_alert_classifier_prompt(post_text: str, pattern: str, is_regex: bool = False) -> str:
    """
    Generate prompt for alert pattern matching.
    
    Args:
        post_text: Text content of the post to analyze
        pattern: Pattern to match against (keyword or regex)
        is_regex: Whether the pattern is a regex or simple keyword
        
    Returns:
        Formatted prompt for alert classification
    """
    pattern_type = "regular expression" if is_regex else "keyword/phrase"
    
    return f"""You are a precise text classifier. Analyze whether the given post text matches the specified pattern.

POST TEXT:
{post_text}

PATTERN TO MATCH: {pattern}
PATTERN TYPE: {pattern_type}

INSTRUCTIONS:
1. Determine if the post text contains or matches the given pattern
2. For keyword/phrase patterns: check for exact word matches (case-insensitive)
3. For regex patterns: evaluate the regular expression against the text
4. Be precise - do not over-interpret or hallucinate matches
5. Consider context and meaning, not just character sequences

IMPORTANT:
- Only return valid JSON
- Be conservative - when in doubt, return false
- Provide a clear, factual reason for your decision
- Do not invent matches that aren't clearly present

OUTPUT FORMAT (JSON only):
{{"matched": true/false, "reason": "Brief explanation of why it matched or didn't match"}}

Response:"""

def get_translation_prompt(text: str, target_lang: str = "en") -> str:
    """
    Generate prompt for text translation.
    
    Args:
        text: Text to translate
        target_lang: Target language code
        
    Returns:
        Formatted translation prompt
    """
    lang_names = {
        "en": "English",
        "uk": "Ukrainian",
        "ru": "Russian", 
        "de": "German",
        "fr": "French",
        "es": "Spanish"
    }
    target_language = lang_names.get(target_lang, "English")
    return f"""Translate the following text to {target_language}. Preserve the meaning and tone while making it natural in the target language.

TEXT TO TRANSLATE:
{text}

INSTRUCTIONS:
- Maintain the original meaning and context
- Use natural, fluent {target_language}
- Preserve any technical terms or proper nouns appropriately
"""
def get_language_detection_prompt(text: str) -> str:
    """
    Generate prompt for language detection (backup to langdetect).
    
    Args:
        text: Text to analyze for language
        
    Returns:
        Language detection prompt
    """
    return f"""Identify the primary language of the following text. Return only the 2-letter ISO language code (e.g., "en", "uk", "ru", "de", "fr", "es").

TEXT:
{text}

INSTRUCTIONS:
- Return only the 2-letter language code
- If multiple languages are present, return the dominant one
- If uncertain, return "en" as fallback

Language code:"""

def get_content_filter_prompt(text: str) -> str:
    """
    Generate prompt for content quality assessment.
    
    Args:
        text: Text to evaluate
        
    Returns:
        Content filter prompt
    """
    return f"""Evaluate the following text for news worthiness and content quality.

TEXT:
{text}

CRITERIA:
- Is this actual news or information?
- Does it contain substantive content?
- Is it spam, advertisement, or low-value content?
- Is it potentially harmful or inappropriate?

Return JSON with your assessment:
{{"is_news_worthy": true/false, "content_quality": "high/medium/low", "reason": "brief explanation"}}

Assessment:"""

def create_digest_prompt(posts: List[Dict[str, Any]], target_lang: str = "en") -> str:
    """
    Create a digest prompt (alias for get_summary_prompt for compatibility).
    
    Args:
        posts: List of posts with keys: channel_handle, text, url, posted_at
        target_lang: Target language for the summary
        
    Returns:
        Formatted prompt for digest creation
    """
    return get_summary_prompt(posts, target_lang)

# Aliases for test compatibility (must be after function definitions)
build_summary_prompt = get_summary_prompt
build_alert_prompt = get_alert_classifier_prompt
