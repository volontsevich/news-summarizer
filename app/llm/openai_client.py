# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""OpenAI API client for summarization/translation."""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
from openai import AsyncOpenAI
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class OpenAIClient:
    """Thin wrapper around OpenAI API with retries, timeouts, and token management."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        
    async def get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client instance."""
        if self._client is None:
            self.settings.require_openai()  # Raises if API key missing
            self._client = AsyncOpenAI(
                api_key=self.settings.OPENAI_API_KEY,
                timeout=30.0,  # 30 second timeout
            )
        return self._client
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters for English).
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Simple heuristic: 1 token per 4 characters (conservative estimate)
        return len(text) // 4 + 1
    
    def truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum allowed tokens
            
        Returns:
            Truncated text that fits within token limit
        """
        if not text:
            return ""
        
        estimated_tokens = self.estimate_tokens(text)
        if estimated_tokens <= max_tokens:
            return text
        
        # Calculate approximate character limit
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Truncate and try to end at a word boundary
        truncated = text[:max_chars]
        
        # Find last space to avoid cutting words
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.8:  # Only if we don't lose too much
            truncated = truncated[:last_space]
        
        logger.warning(f"Truncated text from {len(text)} to {len(truncated)} characters (estimated {estimated_tokens} -> {self.estimate_tokens(truncated)} tokens)")
        
        return truncated + "..."
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError)),
        reraise=True
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        **kwargs
    ) -> str:
        """
        Send chat completion request to OpenAI with retries and token management.
        
        Args:
            messages: Chat messages in OpenAI format
            model: Model to use (defaults to settings)
            max_tokens: Maximum response tokens
            temperature: Response randomness (0.0-2.0)
            **kwargs: Additional parameters for OpenAI API
            
        Returns:
            Generated text response
            
        Raises:
            RuntimeError: If API call fails after retries
        """
        client = await self.get_client()
        
        # Use configured model if not specified
        if model is None:
            model = self.settings.SUMMARY_MODEL
        
        # Set default max_tokens from settings
        if max_tokens is None:
            max_tokens = self.settings.SUMMARY_MAX_TOKENS
        
        # Ensure messages don't exceed input token limits
        # Reserve space for response (rough estimate: 50% of max_tokens for input)
        input_token_limit = max_tokens
        
        # Truncate messages if they're too long
        truncated_messages = []
        for message in messages:
            content = message.get("content", "")
            if self.estimate_tokens(content) > input_token_limit:
                content = self.truncate_to_token_limit(content, input_token_limit)
            
            truncated_messages.append({
                "role": message["role"],
                "content": content
            })
        
        try:
            logger.debug(f"Making OpenAI API call with model={model}, max_tokens={max_tokens}")
            
            response = await client.chat.completions.create(
                model=model,
                messages=truncated_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            if not response.choices or not response.choices[0].message.content:
                raise RuntimeError("OpenAI API returned empty response")
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"OpenAI API successful, response length: {len(result)}")
            
            return result
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI API call: {e}")
            raise RuntimeError(f"Failed to complete OpenAI request: {str(e)}")
    
    async def simple_completion(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1
    ) -> str:
        """
        Simple text completion using chat format.
        
        Args:
            prompt: Input prompt
            model: Model to use
            max_tokens: Maximum response tokens
            temperature: Response randomness
            
        Returns:
            Generated text response
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )

# Global client instance
_openai_client = OpenAIClient()

async def get_openai_client() -> OpenAIClient:
    """Get the global OpenAI client instance."""
    return _openai_client

async def chat_with_openai(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    Convenience function for chat completion.
    
    Args:
        messages: Chat messages
        model: Model to use
        max_tokens: Maximum response tokens
        **kwargs: Additional parameters
        
    Returns:
        Generated response
    """
    client = await get_openai_client()
    return await client.chat_completion(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        **kwargs
    )

async def simple_openai_prompt(prompt: str, **kwargs) -> str:
    """
    Convenience function for simple prompts.
    
    Args:
        prompt: Input prompt
        **kwargs: Additional parameters
        
    Returns:
        Generated response
    """
    client = await get_openai_client()
    return await client.simple_completion(prompt=prompt, **kwargs)
