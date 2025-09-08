# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Telegram ingestion using Telethon."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
from telethon.tl.types import MessageService, MessageEmpty
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class TelegramClientFactory:
    """Factory for creating and managing Telegram client instances."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[TelegramClient] = None
        
    async def get_client(self) -> TelegramClient:
        """Get or create a Telegram client instance."""
        if self._client is None:
            if not self.settings.TELEGRAM_API_ID or not self.settings.TELEGRAM_API_HASH:
                raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")
            
            # Ensure session directory exists
            session_dir = "/data"
            os.makedirs(session_dir, exist_ok=True)
            session_path = os.path.join(session_dir, self.settings.TELEGRAM_SESSION_NAME)
            
            self._client = TelegramClient(
                session_path,
                int(self.settings.TELEGRAM_API_ID),
                self.settings.TELEGRAM_API_HASH,
                timeout=self.settings.TELEGRAM_TIMEOUT
            )
            
            await self._client.start()
            logger.info("Telegram client initialized successfully")
            
        return self._client
    
    async def close(self):
        """Close the Telegram client connection."""
        if self._client:
            await self._client.disconnect()
            self._client = None
            logger.info("Telegram client disconnected")

# Global factory instance
_telegram_factory = TelegramClientFactory()

async def fetch_new_posts(handle: str, last_message_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Fetch new posts from a Telegram channel.
    
    Args:
        handle: Channel handle (e.g., "@channelname" or "channelname")
        last_message_id: Last processed message ID to fetch newer posts
        limit: Maximum number of posts to fetch
        
    Returns:
        List of post dictionaries with keys: message_id, posted_at, text, url
        
    Raises:
        RuntimeError: If channel access fails or API credentials are missing
    """
    settings = get_settings()
    client = await _telegram_factory.get_client()
    posts = []
    
    try:
        # Normalize handle (ensure it starts with @)
        if not handle.startswith('@'):
            handle = f'@{handle}'
        
        logger.info(f"Fetching posts from {handle}, after message_id={last_message_id}, limit={limit}")
        
        # Get the channel entity
        try:
            entity = await client.get_entity(handle)
        except (ChannelPrivateError, UsernameNotOccupiedError) as e:
            logger.error(f"Cannot access channel {handle}: {e}")
            raise RuntimeError(f"Channel {handle} is not accessible")
        
        # Fetch messages
        min_id = last_message_id if last_message_id else 0
        
        async for message in client.iter_messages(
            entity, 
            limit=limit,
            min_id=min_id,
            reverse=True  # Get oldest first
        ):
            # Skip service messages and empty messages
            if isinstance(message, (MessageService, MessageEmpty)):
                continue
                
            # Skip messages without text content for v1
            if not message.text:
                continue
            
            # Extract URL if present
            url = None
            if hasattr(message, 'media') and message.media:
                # For now, just note that media is present
                url = f"https://t.me/{handle.lstrip('@')}/{message.id}"
            
            post_data = {
                'message_id': message.id,
                'posted_at': message.date.replace(tzinfo=timezone.utc) if message.date else datetime.now(timezone.utc),
                'text': message.text,
                'url': url
            }
            posts.append(post_data)
            
            # Rate limiting sleep
            if settings.TELEGRAM_RATE_LIMIT_SLEEP > 0:
                await asyncio.sleep(settings.TELEGRAM_RATE_LIMIT_SLEEP)
        
        logger.info(f"Fetched {len(posts)} posts from {handle}")
        return posts
        
    except FloodWaitError as e:
        logger.warning(f"Rate limited by Telegram API, sleeping for {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
        # Retry once after flood wait
        return await fetch_new_posts(handle, last_message_id, limit)
        
    except Exception as e:
        logger.error(f"Error fetching posts from {handle}: {e}")
        raise RuntimeError(f"Failed to fetch posts from {handle}: {str(e)}")

async def close_telegram_client():
    """Close the global Telegram client connection."""
    await _telegram_factory.close()
