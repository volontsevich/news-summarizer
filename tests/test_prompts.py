"""Test LLM prompt generation."""

import pytest
from datetime import datetime, timezone
from app.llm.prompts import build_summary_prompt, build_alert_prompt


def test_build_summary_prompt_single_post():
    """Test summary prompt generation with single post."""
    posts = [
        {
            "text": "AI company announces breakthrough in language models",
            "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "channel": "TechNews"
        }
    ]
    
    prompt = build_summary_prompt(posts, target_lang="en")
    
    # Should contain the post text
    assert "AI company announces breakthrough" in prompt
    assert "TechNews" in prompt
    assert "2024-01-01" in prompt
    
    # Should contain instructions
    assert "summarize" in prompt.lower()
    assert "english" in prompt.lower() or "en" in prompt.lower()


def test_build_summary_prompt_multiple_posts():
    """Test summary prompt with multiple posts."""
    posts = [
        {
            "text": "First news about technology",
            "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "channel": "TechChannel"
        },
        {
            "text": "Second news about AI developments",
            "date": datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            "channel": "AIChannel"
        }
    ]
    
    prompt = build_summary_prompt(posts, target_lang="es")
    
    # Should contain both posts
    assert "First news about technology" in prompt
    assert "Second news about AI developments" in prompt
    assert "TechChannel" in prompt
    assert "AIChannel" in prompt
    
    # Should request Spanish output
    assert "spanish" in prompt.lower() or "español" in prompt.lower() or "es" in prompt.lower()


def test_build_alert_prompt():
    """Test alert prompt generation."""
    post = {
        "text": "URGENT: Major security vulnerability discovered in popular software",
        "date": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "channel": "SecurityNews"
    }
    
    rule_name = "Security Alerts"
    
    prompt = build_alert_prompt(post, rule_name)
    
    # Should contain post details
    assert "URGENT: Major security vulnerability" in prompt
    assert "SecurityNews" in prompt
    assert "Security Alerts" in prompt
    
    # Should contain alert context
    assert "alert" in prompt.lower()
    assert "triggered" in prompt.lower() or "matched" in prompt.lower()
