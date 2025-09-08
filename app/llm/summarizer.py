# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""LLM-based summarization logic."""

import json
import logging
import re
from typing import List, Optional, Dict, Any
from app.core.config import get_settings
from app.db.models import Post
from app.llm.openai_client import get_openai_client
from app.llm.prompts import get_summary_prompt, get_alert_classifier_prompt

logger = logging.getLogger(__name__)

async def summarize_posts(posts: List[Post], target_lang: str = None) -> str:
    """
    Summarize a list of Telegram posts into a structured Markdown digest.
    
    Handles large inputs by chunking posts based on token limits, summarizing
    in parts, then merging with a final pass for coherence.
    
    Args:
        posts: List of Post model instances to summarize
        target_lang: Target language for summary (defaults to settings)
        
    Returns:
        Markdown-formatted summary digest
        
    Raises:
        RuntimeError: If summarization fails or no valid posts provided
    """
    if not posts:
        logger.warning("No posts provided for summarization")
        return "# No Content Available\n\nNo posts were available for summarization in this time period."
    
    settings = get_settings()
    client = await get_openai_client()
    
    if target_lang is None:
        target_lang = settings.target_language()
    
    logger.info(f"Starting summarization of {len(posts)} posts, target language: {target_lang}")
    
    try:
        # Convert Post models to dict format for prompt generation
        post_dicts = []
        for post in posts:
            post_dict = {
                'channel_handle': post.channel.handle if post.channel else 'unknown',
                'text': post.normalized_text or post.raw_text,
                'url': post.url,
                'posted_at': post.posted_at.isoformat() if post.posted_at else ''
            }
            post_dicts.append(post_dict)
        
        # Check if we need to chunk the posts
        max_tokens = settings.SUMMARY_MAX_TOKENS
        # Reserve tokens for response (roughly 30% of max_tokens)
        input_token_budget = int(max_tokens * 0.7)
        
        # Estimate total tokens needed
        test_prompt = get_summary_prompt(post_dicts[:5], target_lang)  # Sample to estimate
        estimated_tokens_per_post = client.estimate_tokens(test_prompt) // 5 if len(post_dicts) >= 5 else client.estimate_tokens(test_prompt)
        total_estimated_tokens = estimated_tokens_per_post * len(post_dicts)
        
        if total_estimated_tokens <= input_token_budget:
            # Single pass summarization
            logger.debug("Using single-pass summarization")
            summary = await _summarize_single_chunk(post_dicts, target_lang, client)
        else:
            # Multi-chunk summarization
            logger.debug(f"Using multi-chunk summarization (estimated {total_estimated_tokens} tokens)")
            summary = await _summarize_multi_chunk(post_dicts, target_lang, client, input_token_budget)
        
        logger.info(f"Summarization completed, output length: {len(summary)} characters")
        return summary
        
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise RuntimeError(f"Failed to summarize posts: {str(e)}")

async def _summarize_single_chunk(post_dicts: List[Dict[str, Any]], target_lang: str, client) -> str:
    """Summarize all posts in a single API call."""
    prompt = get_summary_prompt(post_dicts, target_lang)
    messages = [{"role": "user", "content": prompt}]
    
    return await client.chat_completion(messages, temperature=0.1)

async def _summarize_multi_chunk(post_dicts: List[Dict[str, Any]], target_lang: str, client, token_budget: int) -> str:
    """Summarize posts in chunks, then merge with a final pass."""
    
    # Determine chunk size based on token budget
    test_prompt = get_summary_prompt(post_dicts[:1], target_lang)
    tokens_per_post = client.estimate_tokens(test_prompt)
    posts_per_chunk = max(1, token_budget // tokens_per_post)
    
    logger.debug(f"Chunking {len(post_dicts)} posts into chunks of ~{posts_per_chunk} posts")
    
    # Generate summaries for each chunk
    chunk_summaries = []
    for i in range(0, len(post_dicts), posts_per_chunk):
        chunk = post_dicts[i:i + posts_per_chunk]
        logger.debug(f"Summarizing chunk {i//posts_per_chunk + 1}: posts {i+1}-{min(i+posts_per_chunk, len(post_dicts))}")
        
        try:
            chunk_summary = await _summarize_single_chunk(chunk, target_lang, client)
            chunk_summaries.append(chunk_summary)
        except Exception as e:
            logger.warning(f"Failed to summarize chunk {i//posts_per_chunk + 1}: {e}")
            continue
    
    if not chunk_summaries:
        raise RuntimeError("All chunk summarizations failed")
    
    # Merge chunk summaries with final pass
    logger.debug(f"Merging {len(chunk_summaries)} chunk summaries")
    return await _merge_summaries(chunk_summaries, target_lang, client)

async def _merge_summaries(summaries: List[str], target_lang: str, client) -> str:
    """Merge multiple summary chunks into a coherent final summary."""
    
    # Create merge prompt
    summaries_text = "\n\n=== SUMMARY SECTION ===\n\n".join(summaries)
    
    merge_prompt = f"""You are a professional editor. Merge the following summary sections into one coherent, well-structured digest in {target_lang}.

SUMMARY SECTIONS TO MERGE:
{summaries_text}

INSTRUCTIONS:
1. Create a single coherent headline that covers all sections
2. Merge and de-duplicate similar bullet points
3. Maintain all important source citations
4. Preserve the "What Changed" section, combining insights
5. Ensure logical flow and grouping
6. Remove redundancy while preserving all significant information
7. Keep the same format: Headline, Key Developments (bullets), What Changed

OUTPUT FORMAT:
# [Merged Headline]

## Key Developments
• [Consolidated bullet points with sources]

## What Changed
[Combined analysis]

Merged summary:"""

    messages = [{"role": "user", "content": merge_prompt}]
    return await client.chat_completion(messages, temperature=0.0)  # Use 0 temperature for consistency

async def classify_alert_match(
    text: str,
    pattern: str,
    is_regex: bool = False,
    language: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Use LLM as a backstop for ambiguous alert pattern matching.
    
    This function should only be called for cases where simple regex/keyword
    matching is insufficient (e.g., semantic matching, context-dependent patterns).
    
    Args:
        text: Text content to analyze
        pattern: Pattern to match against
        is_regex: Whether pattern is a regex (for context)
        language: Language of the text (optional context)
        
    Returns:
        Dict with 'matched' (bool) and 'reason' (str) keys, or None if classification fails
        
    Example:
        result = await classify_alert_match("The economy is struggling", "economic crisis", False)
        # Returns: {"matched": True, "reason": "Text discusses economic difficulties"}
    """
    if not text or not pattern:
        logger.warning("Empty text or pattern provided for alert classification")
        return None
    
    settings = get_settings()
    client = await get_openai_client()
    
    logger.debug(f"LLM alert classification for pattern '{pattern}' (regex: {is_regex})")
    
    try:
        prompt = get_alert_classifier_prompt(text, pattern, is_regex)
        messages = [{"role": "user", "content": prompt}]
        
        response = await client.chat_completion(
            messages,
            temperature=0.0,  # Deterministic classification
            max_tokens=200    # Short response expected
        )
        
        # Parse JSON response
        try:
            result = json.loads(response.strip())
            
            # Validate response format
            if not isinstance(result, dict) or 'matched' not in result or 'reason' not in result:
                logger.error(f"Invalid JSON structure in LLM response: {response}")
                return None
            
            if not isinstance(result['matched'], bool):
                logger.error(f"'matched' field is not boolean: {result['matched']}")
                return None
            
            logger.debug(f"LLM classification result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}, response: {response}")
            return None
    
    except Exception as e:
        logger.error(f"LLM alert classification failed: {e}")
        return None

def should_use_llm_classification(pattern: str, is_regex: bool) -> bool:
    """
    Determine if LLM classification should be used as a backstop.
    
    Args:
        pattern: The pattern to evaluate
        is_regex: Whether it's a regex pattern
        
    Returns:
        True if LLM classification might be helpful for this pattern
    """
    # Use LLM for semantic patterns or complex cases
    semantic_indicators = [
        'sentiment', 'positive', 'negative', 'crisis', 'emergency',
        'important', 'urgent', 'breaking', 'developing', 'analysis'
    ]
    
    # If pattern contains semantic words, LLM might help
    pattern_lower = pattern.lower()
    for indicator in semantic_indicators:
        if indicator in pattern_lower:
            return True
    
    # For very short or very complex regex, LLM might provide better context
    if is_regex and (len(pattern) > 50 or len(pattern) < 5):
        return True
    
    return False
