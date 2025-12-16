"""
Discord integration module for Bear Planner.
Provides functionality to link Discord channels/threads and fetch messages.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

import discord
from discord.ext import commands


class DiscordClient:
    """Discord client for fetching messages from channels/threads."""
    
    def __init__(self, bot_token: Optional[str] = None):
        """
        Initialize Discord client.
        
        Args:
            bot_token: Discord bot token. If None, will try to get from environment.
        """
        self.bot_token = bot_token or os.getenv("DISCORD_BOT_TOKEN")
        self._client: Optional[discord.Client] = None
        self._ready = False
        
    async def connect(self) -> bool:
        """
        Connect to Discord.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        if not self.bot_token:
            return False
            
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.guilds = True
            
            self._client = discord.Client(intents=intents)
            
            @self._client.event
            async def on_ready():
                self._ready = True
            
            # Start client in background
            asyncio.create_task(self._client.start(self.bot_token))
            
            # Wait for ready with timeout
            timeout = 10
            for _ in range(timeout * 10):
                if self._ready:
                    return True
                await asyncio.sleep(0.1)
            
            return False
        except Exception as e:
            print(f"Discord connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Discord."""
        if self._client:
            await self._client.close()
            self._client = None
            self._ready = False
    
    def is_connected(self) -> bool:
        """Check if client is connected and ready."""
        return self._ready and self._client is not None
    
    async def fetch_messages(
        self,
        channel_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from a Discord channel or thread.
        
        Args:
            channel_id: Discord channel or thread ID.
            limit: Maximum number of messages to fetch (default: 50, max: 100).
            
        Returns:
            List of message dictionaries with id, author, content, timestamp.
        """
        if not self.is_connected():
            return []
        
        try:
            channel = self._client.get_channel(channel_id)
            
            if not channel:
                # Try fetching the channel
                channel = await self._client.fetch_channel(channel_id)
            
            if not channel:
                return []
            
            # Limit to max 100 messages
            limit = min(limit, 100)
            
            messages = []
            async for message in channel.history(limit=limit):
                messages.append({
                    "id": str(message.id),
                    "author": {
                        "id": str(message.author.id),
                        "name": message.author.display_name,
                        "username": message.author.name,
                        "avatar_url": str(message.author.display_avatar.url) if message.author.display_avatar else None,
                    },
                    "content": message.content,
                    "timestamp": message.created_at.isoformat(),
                    "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
                    "attachments": [
                        {
                            "id": str(att.id),
                            "filename": att.filename,
                            "url": att.url,
                            "size": att.size,
                        }
                        for att in message.attachments
                    ],
                    "embeds": len(message.embeds) > 0,
                })
            
            return messages
        except discord.NotFound:
            return []
        except discord.Forbidden:
            return []
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []
    
    async def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a Discord channel or thread.
        
        Args:
            channel_id: Discord channel or thread ID.
            
        Returns:
            Dictionary with channel info or None if not found.
        """
        if not self.is_connected():
            return None
        
        try:
            channel = self._client.get_channel(channel_id)
            
            if not channel:
                channel = await self._client.fetch_channel(channel_id)
            
            if not channel:
                return None
            
            info = {
                "id": str(channel.id),
                "name": channel.name,
                "type": str(channel.type),
            }
            
            # Add guild info if available
            if hasattr(channel, "guild") and channel.guild:
                info["guild"] = {
                    "id": str(channel.guild.id),
                    "name": channel.guild.name,
                }
            
            # Add parent channel info for threads
            if isinstance(channel, discord.Thread) and channel.parent:
                info["parent"] = {
                    "id": str(channel.parent.id),
                    "name": channel.parent.name,
                }
            
            return info
        except Exception as e:
            print(f"Error getting channel info: {e}")
            return None


# Global Discord client instance
_discord_client: Optional[DiscordClient] = None


async def get_discord_client() -> Optional[DiscordClient]:
    """
    Get or create the global Discord client instance.
    
    Returns:
        DiscordClient instance or None if token not configured.
    """
    global _discord_client
    
    if _discord_client is None:
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            return None
        
        _discord_client = DiscordClient(token)
        await _discord_client.connect()
    
    return _discord_client


async def disconnect_discord_client():
    """Disconnect and cleanup the global Discord client."""
    global _discord_client
    
    if _discord_client:
        await _discord_client.disconnect()
        _discord_client = None
