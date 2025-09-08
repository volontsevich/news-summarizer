"""Test filtering logic."""

import pytest
from app.utils.filters import should_filter_post, compile_filter_patterns


def test_should_filter_post_matches():
    """Test that posts matching filter patterns are filtered."""
    patterns = ["sports", "football"]
    
    # Should filter sports content
    assert should_filter_post("This is about sports news", patterns) == True
    assert should_filter_post("Football match today", patterns) == True
    assert should_filter_post("The team won the football game", patterns) == True


def test_should_filter_post_no_match():
    """Test that posts not matching filter patterns are not filtered."""
    patterns = ["sports", "football"]
    
    # Should not filter non-sports content
    assert should_filter_post("Technology news today", patterns) == False
    assert should_filter_post("AI breakthrough announcement", patterns) == False
    assert should_filter_post("Economic update", patterns) == False


def test_should_filter_post_case_insensitive():
    """Test that filtering is case insensitive."""
    patterns = ["sports"]
    
    assert should_filter_post("SPORTS news", patterns) == True
    assert should_filter_post("Sports News", patterns) == True
    assert should_filter_post("sports update", patterns) == True


def test_should_filter_post_partial_words():
    """Test filtering with partial word matches."""
    patterns = ["tech"]
    
    assert should_filter_post("Technology breakthrough", patterns) == True
    assert should_filter_post("Biotech company", patterns) == True
    assert should_filter_post("Fintech solutions", patterns) == True


def test_compile_filter_patterns():
    """Test filter pattern compilation."""
    rules = [
        {"pattern": "sports|football", "is_active": True},
        {"pattern": "politics", "is_active": True},
        {"pattern": "inactive", "is_active": False}
    ]
    
    patterns = compile_filter_patterns(rules)
    
    # Should only include active patterns
    assert "sports" in patterns[0]
    assert "football" in patterns[0]
    assert "politics" in patterns[1]
    assert len(patterns) == 2  # inactive pattern excluded


def test_empty_patterns():
    """Test handling of empty filter patterns."""
    assert should_filter_post("Any text", []) == False
    assert compile_filter_patterns([]) == []


def test_complex_patterns():
    """Test complex regex patterns."""
    patterns = [r"\b(crypto|bitcoin|blockchain)\b"]
    
    assert should_filter_post("Bitcoin price surge", patterns) == True
    assert should_filter_post("Blockchain technology", patterns) == True
    assert should_filter_post("Cryptocurrency market", patterns) == False  # crypto not as whole word
