import re
from typing import List, Dict

def should_filter_post(text: str, patterns: List[str]) -> bool:
    """
    Return True if the text matches any of the filter patterns (case-insensitive).
    Patterns can be regex or plain substrings.
    """
    if not patterns:
        return False
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def compile_filter_patterns(rules: List[Dict]) -> List[str]:
    """
    Compile active filter patterns from rules.
    Each rule is a dict with 'pattern' and 'is_active'.
    """
    return [rule['pattern'] for rule in rules if rule.get('is_active')]
