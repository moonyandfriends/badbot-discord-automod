#!/usr/bin/env python3
"""
Discord AutoMod Bot for Railway - Improved Version with Rate Limiting
Monitors AutoMod events, uses ChatGPT to detect scams, bans users across all servers, and sends webhook notifications.
"""

import os
import asyncio
import logging
import aiohttp
import re
import time
import signal
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from urllib.parse import urlparse
from collections import deque
import backoff

import nextcord
from nextcord.ext import commands
import openai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Configuration for a Discord server."""
    guild_id: int
    guild_name: str

@dataclass
class WebhookMessage:
    """Represents a webhook message in the queue."""
    webhook_url: str
    payload: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 3

class WebhookQueue:
    """Queue system for handling webhook messages with retries and rate limiting."""
    
    def __init__(self, session: aiohttp.ClientSession, rate_limiter: 'RateLimiter'):
        self.queue: deque = deque()
        self.session = session
        self.rate_limiter = rate_limiter
        self.processing = False
        self.task: Optional[asyncio.Task] = None
        
    async def add_webhook_message(self, webhook_url: str, payload: Dict[str, Any]) -> None:
        """Add a webhook message to the queue."""
        webhook_msg = WebhookMessage(webhook_url=webhook_url, payload=payload)
        self.queue.append(webhook_msg)
        logger.info(f"Added webhook message to queue. Queue size: {len(self.queue)}")
        
        # Start processing if not already running
        if not self.processing:
            await self.start_processing()
    
    async def start_processing(self) -> None:
        """Start the webhook processing loop."""
        if self.processing:
            return
            
        self.processing = True
        self.task = asyncio.create_task(self._process_queue())
        logger.info("Started webhook queue processing")
    
    async def stop_processing(self) -> None:
        """Stop the webhook processing loop."""
        self.processing = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped webhook queue processing")
    
    async def _process_queue(self) -> None:
        """Process webhook messages in the queue."""
        logger.info("Starting webhook queue processing loop")
        while self.processing:
            if not self.queue:
                await asyncio.sleep(1)
                continue
            
            # Get next webhook message
            webhook_msg = self.queue.popleft()
            logger.info(f"Processing webhook message (queue size: {len(self.queue)})")
            
            # Rate limit check
            await self.rate_limiter.acquire()
            
            # Try to send the webhook
            success = await self._send_webhook_with_retry(webhook_msg)
            
            if not success and webhook_msg.retry_count < webhook_msg.max_retries:
                # Re-queue for retry
                webhook_msg.retry_count += 1
                self.queue.append(webhook_msg)
                logger.info(f"Re-queued webhook message for retry {webhook_msg.retry_count}/{webhook_msg.max_retries}")
            elif not success:
                logger.error(f"Webhook failed after {webhook_msg.max_retries} attempts, dropping message")
            
            # Wait 0.5 seconds before processing next webhook
            logger.info("Waiting 0.5 seconds before processing next webhook...")
            await asyncio.sleep(0.5)
        
        logger.info("Webhook queue processing loop stopped")
    
    async def _send_webhook_with_retry(self, webhook_msg: WebhookMessage) -> bool:
        """Send a webhook message with retry logic."""
        try:
            async with self.session.post(
                webhook_msg.webhook_url, 
                json=webhook_msg.payload, 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 204:
                    logger.info(f"Webhook sent successfully (attempt {webhook_msg.retry_count + 1})")
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status} (attempt {webhook_msg.retry_count + 1})")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error(f"Webhook request timed out (attempt {webhook_msg.retry_count + 1})")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook (attempt {webhook_msg.retry_count + 1}): {e}")
            return False
    
    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return len(self.queue)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed status of the webhook queue."""
        return {
            "queue_size": len(self.queue),
            "processing": self.processing,
            "has_task": self.task is not None
        }

class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
    
    async def acquire(self):
        """Acquire permission to make an API call."""
        now = time.time()
        
        # Remove old calls outside the time window
        while self.calls and now - self.calls[0] > self.time_window:
            self.calls.popleft()
        
        # If we've made too many calls, wait
        if len(self.calls) >= self.max_calls:
            wait_time = self.time_window - (now - self.calls[0])
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
        
        # Add current call
        self.calls.append(now)

class BadBotAutoMod:
    """Discord AutoMod bot that detects scams and bans users across multiple servers."""
    
    def __init__(self):
        self.bot = None
        self.servers: Dict[int, ServerConfig] = {}
        self.webhook_urls: List[str] = []
        self.openai_client = None
        self.processed_users: deque = deque(maxlen=1000)  # Prevent memory leaks
        self.openai_model = "gpt-4o-mini"  # Default model
        self.authorized_users: Set[int] = set()  # Users authorized to use ban/unban commands
        
        # Rate limiters
        self.discord_rate_limiter = RateLimiter(max_calls=50, time_window=60)  # 50 calls per minute
        self.openai_rate_limiter = RateLimiter(max_calls=10, time_window=60)   # 10 calls per minute
        self.webhook_rate_limiter = RateLimiter(max_calls=30, time_window=60)  # 30 calls per minute
        
        # Connection pooling
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Webhook queue
        self.webhook_queue: Optional[WebhookQueue] = None
        
        # Graceful shutdown
        self.shutdown_event = asyncio.Event()
        
        # Domain whitelist - trusted domains that won't trigger ChatGPT analysis
        self.whitelisted_domains: Set[str] = set()
        
    def validate_webhook_url(self, url: str) -> bool:
        """Validate that a webhook URL is properly formatted."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['http', 'https'] and
                ('discord.com' in parsed.netloc or 'discordapp.com' in parsed.netloc) and
                '/api/webhooks/' in parsed.path
            )
        except Exception:
            return False
        
    def validate_avatar_url(self, url: str) -> bool:
        """Validate that an avatar URL is properly formatted and accessible."""
        try:
            parsed = urlparse(url)
            # Check if it's a valid HTTP/HTTPS URL
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check if it has a valid image extension
            valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
            if not any(parsed.path.lower().endswith(ext) for ext in valid_extensions):
                return False
                
            return True
        except Exception:
            return False

    def load_config(self) -> None:
        """Load configuration from environment variables."""
        logger.info("Loading configuration from environment variables...")
        
        # Load servers configuration
        servers_env = os.environ.get("badbot_automod_servers")
        if not servers_env:
            raise ValueError("badbot_automod_servers environment variable is required")
            
        # Parse servers in format: guildID|guildName,guildID2|guildName2
        server_pairs = servers_env.split(',')
        
        for pair in server_pairs:
            if '|' in pair:
                parts = pair.strip().split('|')
                if len(parts) == 2:
                    guild_id_str, guild_name = parts
                    try:
                        guild_id = int(guild_id_str.strip())
                        server_config = ServerConfig(
                            guild_id=guild_id,
                            guild_name=guild_name.strip()
                        )
                        self.servers[guild_id] = server_config
                        logger.info(f"Loaded server: {guild_name} ({guild_id})")
                    except ValueError:
                        logger.warning(f"Invalid server ID format: {pair}")
                        continue
                else:
                    logger.warning(f"Invalid server format (expected guildID|guildName): {pair}")
                    continue
                    
        if not self.servers:
            raise ValueError("No valid servers found in badbot_automod_servers")
            
        logger.info(f"Loaded {len(self.servers)} servers from environment")
        
        # Load webhook URLs
        webhooks_env = os.environ.get("badbot_automod_webhookurls")
        if not webhooks_env:
            raise ValueError("badbot_automod_webhookurls environment variable is required")
            
        # Validate webhook URLs
        raw_urls = [url.strip() for url in webhooks_env.split(',') if url.strip()]
        for url in raw_urls:
            if self.validate_webhook_url(url):
                self.webhook_urls.append(url)
                logger.info(f"Loaded valid webhook: {url[:50]}...")
            else:
                logger.warning(f"Invalid webhook URL format: {url[:50]}...")
                
        if not self.webhook_urls:
            logger.warning("No valid webhook URLs found in badbot_automod_webhookurls. Webhook notifications will be disabled.")
        else:
            logger.info(f"Loaded {len(self.webhook_urls)} valid webhook URLs")
        
        # Load webhook avatar URL (optional)
        self.webhook_avatar_url = os.environ.get("badbot_automod_webhook_avatar")
        if self.webhook_avatar_url:
            if self.validate_avatar_url(self.webhook_avatar_url):
                logger.info(f"Using custom webhook avatar: {self.webhook_avatar_url[:50]}...")
            else:
                logger.warning(f"Invalid avatar URL format: {self.webhook_avatar_url[:50]}...")
                self.webhook_avatar_url = None
        
        if not self.webhook_avatar_url:
            # Default security/shield icon - simple and reliable
            self.webhook_avatar_url = "https://i.imgur.com/8tBXd6L.png"
            logger.info("Using default webhook avatar (shield icon)")
        
        # Load optional OpenAI model
        self.openai_model = os.environ.get("openai_model", "gpt-4o-mini")
        logger.info(f"Using OpenAI model: {self.openai_model}")
        
        # Load authorized users for ban/unban commands
        authorized_users_env = os.environ.get("badbot_authorized_users")
        if authorized_users_env:
            # Parse comma-separated user IDs
            user_ids = [uid.strip() for uid in authorized_users_env.split(',') if uid.strip()]
            for user_id_str in user_ids:
                try:
                    user_id = int(user_id_str)
                    self.authorized_users.add(user_id)
                    logger.info(f"Authorized user: {user_id}")
                except ValueError:
                    logger.warning(f"Invalid user ID format: {user_id_str}")
            
            if self.authorized_users:
                logger.info(f"Loaded {len(self.authorized_users)} authorized users for ban/unban commands")
            else:
                logger.warning("No valid authorized users found. Ban/unban commands will be disabled.")
        else:
            logger.warning("badbot_authorized_users environment variable not set. Ban/unban commands will be disabled.")
        
        # Load domain whitelist
        whitelist_env = os.environ.get("badbot_domain_whitelist")
        if whitelist_env:
            # Parse comma-separated domains
            domains = [domain.strip().lower() for domain in whitelist_env.split(',') if domain.strip()]
            self.whitelisted_domains = set(domains)
            logger.info(f"Loaded {len(self.whitelisted_domains)} whitelisted domains")
        else:
            logger.info("No domain whitelist configured. All messages will be analyzed by ChatGPT.")
        
    def load_credentials(self) -> str:
        """Load Discord token and OpenAI key from environment variables."""
        logger.info("Loading credentials...")
        
        # Load Discord token
        discord_token = os.environ.get("badbot_discord_token")
        if not discord_token:
            raise ValueError("badbot_discord_token environment variable is required")
            
        # Validate Discord token format
        if not (discord_token.startswith(('MTA', 'MTI', 'OD', 'ND', 'Nz')) or len(discord_token) > 50):
            logger.warning("Discord token format looks suspicious")
            
        # Load OpenAI key
        openai_key = os.environ.get("badbot_openai_key")
        if not openai_key:
            raise ValueError("badbot_openai_key environment variable is required")
            
        # Validate OpenAI key format
        if not openai_key.startswith('sk-'):
            logger.warning("OpenAI key format looks suspicious (should start with 'sk-')")
            
        # Initialize OpenAI client
        try:
            # Debug: Log all environment variables that might cause issues
            logger.info("Checking environment variables...")
            for key, value in os.environ.items():
                if any(term in key.lower() for term in ['proxy', 'http', 'https', 'openai']):
                    logger.info(f"Found potentially problematic env var: {key}={value[:20]}...")
            
            # Clear any problematic environment variables that might interfere
            # Remove any proxy-related environment variables that might cause issues
            cleared_vars = []
            for key in list(os.environ.keys()):
                if any(term in key.lower() for term in ['proxy', 'http_proxy', 'https_proxy', 'all_proxy']):
                    logger.info(f"Removing environment variable: {key}")
                    cleared_vars.append(key)
                    del os.environ[key]
            
            if cleared_vars:
                logger.info(f"Cleared {len(cleared_vars)} environment variables: {cleared_vars}")
            
            # Use modern OpenAI API method
            self.openai_client = openai.OpenAI(api_key=openai_key)
            logger.info("OpenAI client initialized successfully using modern API")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            
            # Try alternative initialization method
            try:
                logger.info("Trying alternative OpenAI initialization...")
                self.openai_client = openai.OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized with alternative method")
            except Exception as e2:
                logger.error(f"Alternative initialization also failed: {e2}")
                raise e2
            
        logger.info("Credentials loaded successfully")
        
        return discord_token

    async def check_user_post_count(self, user_id: int, guild: nextcord.Guild) -> int:
        """Check how many messages a user has posted across all accessible channels in a guild."""
        try:
            member = guild.get_member(user_id)
            if not member:
                logger.info(f"User {user_id} is not a member of {guild.name}")
                return 0
            
            total_posts = 0
            
            # Check accessible text channels
            for channel in guild.text_channels:
                try:
                    # Check if bot can read message history in this channel
                    if not channel.permissions_for(guild.me).read_message_history:
                        continue
                    
                    # Count user's messages in this channel (limit to recent messages for performance)
                    async for message in channel.history(limit=100):
                        if message.author.id == user_id:
                            total_posts += 1
                            
                            # Early exit if we've found enough posts
                            if total_posts > 6:
                                logger.info(f"User {user_id} has >6 posts in {guild.name}, stopping count at {total_posts}")
                                return total_posts
                                
                except (nextcord.Forbidden, nextcord.HTTPException) as e:
                    # Skip channels we can't access
                    logger.debug(f"Cannot access channel {channel.name}: {e}")
                    continue
            
            logger.info(f"User {user_id} has {total_posts} posts in {guild.name}")
            return total_posts
            
        except Exception as e:
            logger.error(f"Error checking post count for user {user_id} in {guild.name}: {e}")
            return 0

    async def check_user_post_count_across_servers(self, user_id: int) -> int:
        """Check user's total post count across all accessible servers."""
        if not self.bot:
            return 0
        
        total_posts = 0
        
        for guild_id in self.servers.keys():
            guild = self.bot.get_guild(guild_id)
            if guild:
                posts_in_guild = await self.check_user_post_count(user_id, guild)
                total_posts += posts_in_guild
                
                # Early exit if we've found enough posts
                if total_posts > 6:
                    logger.info(f"User {user_id} has >6 total posts across servers, stopping count at {total_posts}")
                    return total_posts
        
        logger.info(f"User {user_id} has {total_posts} total posts across all accessible servers")
        return total_posts

    def is_authorized_user(self, user_id: int) -> bool:
        """Check if a user is authorized to use ban/unban commands."""
        return user_id in self.authorized_users

    def contains_whitelisted_domain(self, content: str) -> bool:
        """Check if the message content contains any whitelisted domains."""
        if not self.whitelisted_domains:
            return False
        
        # Convert content to lowercase for case-insensitive matching
        content_lower = content.lower()
        
        # Check if any whitelisted domain is present in the content
        for domain in self.whitelisted_domains:
            if domain in content_lower:
                logger.info(f"Found whitelisted domain '{domain}' in message content")
                return True
        
        return False

    async def send_ban_webhook_notification(self, action: str, target_user_id: int, target_username: str, 
                                          moderator_id: int, moderator_username: str, guild_name: str, 
                                          notes: str, success: bool = True) -> None:
        """Send webhook notification for ban/unban actions."""
        if not self.webhook_urls or not self.webhook_queue:
            return
            
        # Clean up notes - replace line breaks with spaces
        cleaned_notes = notes.replace('\n', ' ').replace('\r', ' ') if notes else "No notes provided"
        
        # Set color based on action and success
        if action.lower() == "ban":
            color = 0xFF0000 if success else 0xFF8C00  # Red for successful ban, orange for failed
            emoji = "🔨" if success else "⚠️"
            title = f"{emoji} User {'Banned' if success else 'Ban Failed'}"
        else:  # unban
            color = 0x00FF00 if success else 0xFF8C00  # Green for successful unban, orange for failed
            emoji = "🔓" if success else "⚠️"
            title = f"{emoji} User {'Unbanned' if success else 'Unban Failed'}"
        
        # Create embed message
        embed_data = {
            "title": title,
            "description": f"**Target:** <@{target_user_id}> ({target_user_id})\n**Moderator:** <@{moderator_id}> ({moderator_id})\n**Server:** {guild_name}",
            "color": color,
            "timestamp": nextcord.utils.utcnow().isoformat()
        }
        
        # Only add Notes field if actual notes were provided (not default message)
        if cleaned_notes and cleaned_notes.lower() != "no notes provided":
            embed_data["fields"] = [
                {
                    "name": "Notes:",
                    "value": f"```{cleaned_notes[:1000]}```",
                    "inline": False
                }
            ]
        
        # Add to webhook queue for each webhook URL
        for webhook_url in self.webhook_urls:
            webhook_data = {
                "username": "Bad Bot - Moderation",
                "embeds": [embed_data]
            }
            
            # Add avatar URL if valid
            if self.webhook_avatar_url and self.validate_avatar_url(self.webhook_avatar_url):
                webhook_data["avatar_url"] = self.webhook_avatar_url
            
            await self.webhook_queue.add_webhook_message(webhook_url, webhook_data)

    async def send_mass_action_webhook_notification(self, action: str, target_user_id: int, target_username: str, 
                                                   moderator_id: int, moderator_username: str, notes: str, 
                                                   results: Dict[int, bool], originating_guild_name: str = None) -> None:
        """Send a single webhook notification for mass ban/unban actions with summary."""
        if not self.webhook_urls or not self.webhook_queue:
            return
            
        # Extract just the user-provided notes (remove prefix like "Mass ban by username: ")
        if notes and ": " in notes:
            # Split on first ": " and take everything after it
            user_notes = notes.split(": ", 1)[1].strip()
        else:
            user_notes = notes if notes else "No notes provided"
        
        # Clean up notes
        cleaned_notes = user_notes.replace('\n', ' ').replace('\r', ' ')
        
        # Calculate success statistics
        successful_actions = sum(1 for success in results.values() if success)
        total_servers = len(results)
        failed_actions = total_servers - successful_actions
        
        # Set color and emoji based on action and results
        if action.lower() == "mass ban":
            if successful_actions == total_servers:
                color = 0xFF0000  # Red for complete success
                emoji = "🔨"
                title = f"{emoji} Mass Ban Complete"
                result_text = f"Successfully banned from **all {total_servers} servers**"
            elif successful_actions > 0:
                color = 0xFF8C00  # Orange for partial success
                emoji = "⚠️"
                title = f"{emoji} Mass Ban Partial"
                result_text = f"Banned from **{successful_actions}/{total_servers} servers** ({failed_actions} failed)"
            else:
                color = 0x808080  # Gray for complete failure
                emoji = "❌"
                title = f"{emoji} Mass Ban Failed"
                result_text = f"**Failed to ban from any servers** (0/{total_servers})"
        else:  # mass unban
            if successful_actions == total_servers:
                color = 0x00FF00  # Green for complete success
                emoji = "🔓"
                title = f"{emoji} Mass Unban Complete"
                result_text = f"Successfully unbanned from **all {total_servers} servers**"
            elif successful_actions > 0:
                color = 0xFF8C00  # Orange for partial success
                emoji = "⚠️"
                title = f"{emoji} Mass Unban Partial"
                result_text = f"Unbanned from **{successful_actions}/{total_servers} servers** ({failed_actions} failed)"
            else:
                color = 0x808080  # Gray for complete failure
                emoji = "❌"
                title = f"{emoji} Mass Unban Failed"
                result_text = f"**Failed to unban from any servers** (0/{total_servers})"
        
        # Create description with originating server info
        description_parts = [
            f"**Target:** <@{target_user_id}> ({target_user_id})",
            f"**Moderator:** <@{moderator_id}> ({moderator_id})",
            f"**Result:** {result_text}"
        ]
        
        if originating_guild_name:
            description_parts.append(f"**Originated in:** {originating_guild_name}")
        
        # Create embed message
        embed_data = {
            "title": title,
            "description": "\n".join(description_parts),
            "color": color,
            "timestamp": nextcord.utils.utcnow().isoformat()
        }
        
        # Only add Notes field if actual notes were provided (not default message)
        if cleaned_notes and cleaned_notes.lower() != "no notes provided":
            embed_data["fields"] = [
                {
                    "name": "Notes:",
                    "value": f"```{cleaned_notes[:1000]}```",
                    "inline": False
                }
            ]
        
        # Add to webhook queue for each webhook URL
        for webhook_url in self.webhook_urls:
            webhook_data = {
                "username": "Bad Bot - Mass Moderation",
                "embeds": [embed_data]
            }
            
            # Add avatar URL if valid
            if self.webhook_avatar_url and self.validate_avatar_url(self.webhook_avatar_url):
                webhook_data["avatar_url"] = self.webhook_avatar_url
            
            await self.webhook_queue.add_webhook_message(webhook_url, webhook_data)

    async def mass_ban_user(self, user_id: int, reason: str, moderator_id: int, moderator_username: str, originating_guild_name: str = None) -> Dict[int, bool]:
        """Ban user from all configured servers and log to webhooks."""
        ban_results = {}
        
        if not self.bot:
            logger.error("Bot not initialized")
            return ban_results
        
        # Protect authorized users from being banned
        if self.is_authorized_user(user_id):
            logger.warning(f"Attempted to ban authorized user {user_id} by {moderator_username} ({moderator_id})")
            return ban_results
        
        # Get target user info
        try:
            target_user = await self.bot.fetch_user(user_id)
            target_username = target_user.display_name if target_user else f"Unknown User ({user_id})"
        except:
            target_username = f"Unknown User ({user_id})"
        
        for guild_id, server_config in self.servers.items():
            # Rate limit check
            await self.discord_rate_limiter.acquire()
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Could not find guild {server_config.guild_name} ({guild_id})")
                ban_results[guild_id] = False
                continue
                
            try:
                # Check if user is already banned
                try:
                    ban_entry = await guild.fetch_ban(nextcord.Object(user_id))
                    if ban_entry:
                        logger.info(f"User {user_id} already banned in {server_config.guild_name}")
                        ban_results[guild_id] = True
                        continue
                except nextcord.NotFound:
                    pass
                
                # Get member object and ban
                member = guild.get_member(user_id)
                if member:
                    await guild.ban(member, reason=reason, delete_message_days=1)
                else:
                    # Try to ban by user ID even if not a member
                    user_obj = await self.bot.fetch_user(user_id)
                    await guild.ban(user_obj, reason=reason, delete_message_days=1)
                
                logger.info(f"Mass banned user {user_id} from {server_config.guild_name}")
                ban_results[guild_id] = True
                    
                # Rate limiting delay
                await asyncio.sleep(2)
                
            except nextcord.Forbidden:
                logger.error(f"No permission to ban in {server_config.guild_name}")
                ban_results[guild_id] = False
            except nextcord.HTTPException as e:
                logger.error(f"HTTP error mass banning user {user_id} from {server_config.guild_name}: {e}")
                ban_results[guild_id] = False
            except Exception as e:
                logger.error(f"Unexpected error mass banning user {user_id} from {server_config.guild_name}: {e}")
                ban_results[guild_id] = False
        
        # Send single webhook notification with summary
        await self.send_mass_action_webhook_notification(
            "mass ban", user_id, target_username, moderator_id, moderator_username, reason, ban_results, originating_guild_name
        )
                
        return ban_results

    async def mass_unban_user(self, user_id: int, reason: str, moderator_id: int, moderator_username: str, originating_guild_name: str = None) -> Dict[int, bool]:
        """Unban user from all configured servers and log to webhooks."""
        unban_results = {}
        
        if not self.bot:
            logger.error("Bot not initialized")
            return unban_results
        
        # Get target user info
        try:
            target_user = await self.bot.fetch_user(user_id)
            target_username = target_user.display_name if target_user else f"Unknown User ({user_id})"
        except:
            target_username = f"Unknown User ({user_id})"
        
        for guild_id, server_config in self.servers.items():
            # Rate limit check
            await self.discord_rate_limiter.acquire()
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Could not find guild {server_config.guild_name} ({guild_id})")
                unban_results[guild_id] = False
                continue
                
            try:
                # Check if user is actually banned
                try:
                    ban_entry = await guild.fetch_ban(nextcord.Object(user_id))
                    if not ban_entry:
                        logger.info(f"User {user_id} not banned in {server_config.guild_name}")
                        unban_results[guild_id] = True
                        continue
                except nextcord.NotFound:
                    logger.info(f"User {user_id} not banned in {server_config.guild_name}")
                    unban_results[guild_id] = True
                    continue
                
                # Unban the user
                user_obj = await self.bot.fetch_user(user_id)
                await guild.unban(user_obj, reason=reason)
                
                logger.info(f"Mass unbanned user {user_id} from {server_config.guild_name}")
                unban_results[guild_id] = True
                    
                # Rate limiting delay
                await asyncio.sleep(2)
                
            except nextcord.Forbidden:
                logger.error(f"No permission to unban in {server_config.guild_name}")
                unban_results[guild_id] = False
            except nextcord.HTTPException as e:
                logger.error(f"HTTP error mass unbanning user {user_id} from {server_config.guild_name}: {e}")
                unban_results[guild_id] = False
            except Exception as e:
                logger.error(f"Unexpected error mass unbanning user {user_id} from {server_config.guild_name}: {e}")
                unban_results[guild_id] = False
        
        # Send single webhook notification with summary
        await self.send_mass_action_webhook_notification(
            "mass unban", user_id, target_username, moderator_id, moderator_username, reason, unban_results, originating_guild_name
        )
                
        return unban_results

    async def single_ban_user(self, user_id: int, guild: nextcord.Guild, reason: str, moderator_id: int, moderator_username: str) -> bool:
        """Ban user from a single server and log to webhooks."""
        # Protect authorized users from being banned
        if self.is_authorized_user(user_id):
            logger.warning(f"Attempted to ban authorized user {user_id} by {moderator_username} ({moderator_id}) in {guild.name}")
            return False
        
        # Rate limit check
        await self.discord_rate_limiter.acquire()
        
        # Get target user info and configured server name
        try:
            target_user = await self.bot.fetch_user(user_id)
            target_username = target_user.display_name if target_user else f"Unknown User ({user_id})"
        except:
            target_username = f"Unknown User ({user_id})"
        
        # Get configured server name for webhook
        server_config = self.servers.get(guild.id)
        server_display_name = server_config.guild_name if server_config else guild.name
        
        try:
            # Check if user is already banned
            try:
                ban_entry = await guild.fetch_ban(nextcord.Object(user_id))
                if ban_entry:
                    logger.info(f"User {user_id} already banned in {guild.name}")
                    await self.send_ban_webhook_notification(
                        "ban", user_id, target_username, moderator_id, moderator_username,
                        server_display_name, f"{reason} (already banned)", success=True
                    )
                    return True
            except nextcord.NotFound:
                pass
            
            # Get member object and ban
            member = guild.get_member(user_id)
            if member:
                await guild.ban(member, reason=reason, delete_message_days=1)
            else:
                # Try to ban by user ID even if not a member
                user_obj = await self.bot.fetch_user(user_id)
                await guild.ban(user_obj, reason=reason, delete_message_days=1)
            
            logger.info(f"Banned user {user_id} from {guild.name}")
            
            # Send success webhook
            await self.send_ban_webhook_notification(
                "ban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, reason, success=True
            )
            
            return True
                
        except nextcord.Forbidden:
            logger.error(f"No permission to ban in {guild.name}")
            await self.send_ban_webhook_notification(
                "ban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (no permission)", success=False
            )
            return False
        except nextcord.HTTPException as e:
            logger.error(f"HTTP error banning user {user_id} from {guild.name}: {e}")
            await self.send_ban_webhook_notification(
                "ban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (HTTP error: {e})", success=False
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error banning user {user_id} from {guild.name}: {e}")
            await self.send_ban_webhook_notification(
                "ban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (error: {e})", success=False
            )
            return False

    async def single_unban_user(self, user_id: int, guild: nextcord.Guild, reason: str, moderator_id: int, moderator_username: str) -> bool:
        """Unban user from a single server and log to webhooks."""
        # Rate limit check
        await self.discord_rate_limiter.acquire()
        
        # Get target user info and configured server name
        try:
            target_user = await self.bot.fetch_user(user_id)
            target_username = target_user.display_name if target_user else f"Unknown User ({user_id})"
        except:
            target_username = f"Unknown User ({user_id})"
        
        # Get configured server name for webhook
        server_config = self.servers.get(guild.id)
        server_display_name = server_config.guild_name if server_config else guild.name
        
        try:
            # Check if user is actually banned
            try:
                ban_entry = await guild.fetch_ban(nextcord.Object(user_id))
                if not ban_entry:
                    logger.info(f"User {user_id} not banned in {guild.name}")
                    await self.send_ban_webhook_notification(
                        "unban", user_id, target_username, moderator_id, moderator_username,
                        server_display_name, f"{reason} (not banned)", success=True
                    )
                    return True
            except nextcord.NotFound:
                logger.info(f"User {user_id} not banned in {guild.name}")
                await self.send_ban_webhook_notification(
                    "unban", user_id, target_username, moderator_id, moderator_username,
                    server_display_name, f"{reason} (not banned)", success=True
                )
                return True
            
            # Unban the user
            user_obj = await self.bot.fetch_user(user_id)
            await guild.unban(user_obj, reason=reason)
            
            logger.info(f"Unbanned user {user_id} from {guild.name}")
            
            # Send success webhook
            await self.send_ban_webhook_notification(
                "unban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, reason, success=True
            )
            
            return True
                
        except nextcord.Forbidden:
            logger.error(f"No permission to unban in {guild.name}")
            await self.send_ban_webhook_notification(
                "unban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (no permission)", success=False
            )
            return False
        except nextcord.HTTPException as e:
            logger.error(f"HTTP error unbanning user {user_id} from {guild.name}: {e}")
            await self.send_ban_webhook_notification(
                "unban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (HTTP error: {e})", success=False
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error unbanning user {user_id} from {guild.name}: {e}")
            await self.send_ban_webhook_notification(
                "unban", user_id, target_username, moderator_id, moderator_username,
                server_display_name, f"{reason} (error: {e})", success=False
            )
            return False

    @backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APIError), max_tries=3)
    async def check_gpt_for_scam(self, content: str) -> bool:
        """Check if content is a scam using ChatGPT with retry logic."""
        # Rate limit check
        await self.openai_rate_limiter.acquire()
        
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return False
        
        system_prompt = (
            "You are a strict content evaluator focusing on scam detection. "
            "Not all external links are suspicious; however, messages containing "
            "Discord invite URLs, link shorteners, offers for Web3.0 jobs, "
            "or messages that appear to recruit for jobs are also likely to be scams. "
            "Additionally, messages from people promising easy earnings or investment opportunities "
            "are highly suspicious. However, people looking for assistance, support, and help "
            "are typically NOT scammers - genuine users often ask questions, request guidance, "
            "or seek troubleshooting help. If the content contains any scam elements or seems to fit "
            "the pattern of scam behavior, consider it a scam. Otherwise, if it appears to be a "
            "legitimate request for help or support, it should NOT be considered a scam."
        )

        user_prompt = (
            f"The following message was flagged by AutoMod:\n\n"
            f"\"{content[:500]}\"\n\n"  # Limit content length
            "Is this message a scam? Start your answer with 'YES:' or 'NO:'."
        )

        try:
            logger.info("Sending content to ChatGPT for analysis...")
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,
                temperature=0.0
            )
            
            # Better error handling for response
            if not response.choices or not response.choices[0].message:
                logger.error("OpenAI returned empty response")
                return False
                
            ai_reply = response.choices[0].message.content
            if not ai_reply:
                logger.error("OpenAI returned empty message content")
                return False
                
            ai_reply = ai_reply.strip()
            logger.info(f"ChatGPT response: {ai_reply}")
            
            return ai_reply.lower().startswith("yes:")
            
        except openai.RateLimitError:
            logger.error("OpenAI rate limit exceeded")
            raise  # Let backoff handle retry
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise  # Let backoff handle retry
        except Exception as e:
            logger.error(f"Error checking content with ChatGPT: {e}")
            return False
            
    async def ban_user_from_all_servers(self, user_id: int, reason: str) -> Dict[int, bool]:
        """Ban user from all configured servers with rate limiting and retry logic."""
        ban_results = {}
        
        if not self.bot:
            logger.error("Bot not initialized")
            return ban_results
        
        # Protect authorized users from being banned by automod
        if self.is_authorized_user(user_id):
            logger.warning(f"Automod attempted to ban authorized user {user_id}, blocking action")
            return ban_results
        
        for guild_id, server_config in self.servers.items():
            # Rate limit check
            await self.discord_rate_limiter.acquire()
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Could not find guild {server_config.guild_name} ({guild_id})")
                ban_results[guild_id] = False
                continue
                
            try:
                # Check if user is already banned
                try:
                    ban_entry = await guild.fetch_ban(nextcord.Object(user_id))
                    if ban_entry:
                        logger.info(f"User {user_id} already banned in {server_config.guild_name}")
                        ban_results[guild_id] = True
                        continue
                except nextcord.NotFound:
                    # User is not banned, proceed with ban
                    pass
                
                # Get member object
                member = guild.get_member(user_id)
                if member:
                    await guild.ban(member, reason=reason, delete_message_days=1)
                    logger.info(f"Banned user {user_id} from {server_config.guild_name}")
                    ban_results[guild_id] = True
                else:
                    # Try to ban by user ID even if not a member
                    user_obj = await self.bot.fetch_user(user_id)
                    await guild.ban(user_obj, reason=reason, delete_message_days=1)
                    logger.info(f"Banned user {user_id} (not a member) from {server_config.guild_name}")
                    ban_results[guild_id] = True
                    
                # Rate limiting delay
                await asyncio.sleep(2)
                
            except nextcord.Forbidden:
                logger.error(f"No permission to ban in {server_config.guild_name}")
                ban_results[guild_id] = False
            except nextcord.HTTPException as e:
                logger.error(f"HTTP error banning user {user_id} from {server_config.guild_name}: {e}")
                ban_results[guild_id] = False
            except Exception as e:
                logger.error(f"Unexpected error banning user {user_id} from {server_config.guild_name}: {e}")
                ban_results[guild_id] = False
                
        return ban_results
        
    async def send_webhook_notifications(self, user_id: int, username: str, 
                                       message_content: str, source_guild_name: str,
                                       ban_results: Dict[int, bool]) -> None:
        """Add webhook notifications to the queue for processing."""
        if not self.webhook_urls:
            logger.info("No webhook URLs configured, skipping notifications")
            return
            
        if not self.webhook_queue:
            logger.error("Webhook queue not initialized")
            return
            
        # Clean up message content - replace line breaks with spaces
        cleaned_content = message_content.replace('\n', ' ').replace('\r', ' ')
        
        # Create embed message
        embed_data = {
            "title": "🔨 Scammer Banned",
            "description": f"**User:** <@{user_id}> ({user_id})\n**Source Server:** {source_guild_name}",
            "color": 0xFF0000,  # Red color
            "fields": [
                {
                    "name": "Scam Message:",
                    "value": f"```{cleaned_content[:1000]}```",
                    "inline": False
                }
            ]
        }
        
        # Add to webhook queue for each webhook URL
        for i, webhook_url in enumerate(self.webhook_urls):
            webhook_data = {
                "username": "Bad Bot",
                "embeds": [embed_data]
            }
            
            # Only add avatar_url if it's valid
            if self.webhook_avatar_url and self.validate_avatar_url(self.webhook_avatar_url):
                webhook_data["avatar_url"] = self.webhook_avatar_url
                logger.debug(f"Adding avatar URL to webhook {i+1}: {self.webhook_avatar_url[:50]}...")
            else:
                logger.warning(f"Skipping avatar URL for webhook {i+1} - invalid or missing")
            
            await self.webhook_queue.add_webhook_message(webhook_url, webhook_data)
            logger.info(f"Added webhook {i+1} to queue")
        
        # Log queue status
        queue_status = self.webhook_queue.get_queue_status()
        logger.info(f"Webhook queue status: {queue_status}")

    def get_webhook_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get the current status of the webhook queue."""
        if self.webhook_queue:
            return self.webhook_queue.get_queue_status()
        return None

    async def handle_automod_event(self, payload: nextcord.AutoModerationActionExecution) -> None:
        """Handle AutoMod action execution events with error recovery."""
        try:
            logger.info(f"Received AutoMod event from guild {payload.guild_id}")
            
            # Only process message blocks
            if payload.action.type != nextcord.AutoModerationActionType.block_message:
                logger.info("Action is not block_message, ignoring")
                return
                
            # Check if this is from one of our monitored servers
            guild_id = payload.guild_id
            if guild_id not in self.servers:
                logger.info(f"Event from unmonitored server {guild_id}, ignoring")
                return
                
            # Get user ID and check for duplicates
            user_id = payload.member_id
            if not user_id:
                logger.warning("No user ID in AutoMod payload")
                return
                
            if user_id in self.processed_users:
                logger.info(f"User {user_id} already processed recently, skipping")
                return
                
            server_config = self.servers[guild_id]
            
            if not self.bot:
                logger.error("Bot not initialized")
                return
                
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                logger.warning(f"Could not find guild {guild_id}")
                return
                
            logger.info(f"Processing AutoMod event from {server_config.guild_name}")
            
            # Get user information
            member = guild.get_member(user_id) if user_id else None
            username = member.display_name if member else f"Unknown User ({user_id})"
            
            # Get blocked content
            blocked_content = payload.content or payload.matched_keyword or ""
            if not blocked_content.strip():
                logger.info("No content to analyze, skipping")
                return
                
            logger.info(f"Analyzing content from {username}: {blocked_content[:100]}...")
            
            # Check user's post count across all servers before querying ChatGPT
            user_post_count = await self.check_user_post_count_across_servers(user_id)
            
            if user_post_count > 6:
                logger.info(f"User {username} ({user_id}) has {user_post_count} posts across servers. Skipping ChatGPT analysis - likely not a scammer.")
                return
            
            logger.info(f"User {username} ({user_id}) has only {user_post_count} posts. Proceeding with domain whitelist check.")
            
            # Check if message contains whitelisted domains
            if self.contains_whitelisted_domain(blocked_content):
                logger.info(f"Message from {username} ({user_id}) contains whitelisted domain. Skipping ChatGPT analysis.")
                return
            
            logger.info(f"No whitelisted domains found in message from {username} ({user_id}). Proceeding with ChatGPT analysis.")
            
            # Check with ChatGPT
            is_scam = await self.check_gpt_for_scam(blocked_content)
            
            if is_scam:
                logger.info(f"ChatGPT confirmed scam from {username} ({user_id})")
                
                # Mark user as processed to prevent duplicates
                self.processed_users.append(user_id)
                
                # Ban user from all servers
                ban_results = await self.ban_user_from_all_servers(user_id, "Scam detected by ChatGPT")
                
                # Send webhook notifications using server name from configuration
                await self.send_webhook_notifications(
                    user_id=user_id,
                    username=username,
                    message_content=blocked_content,
                    source_guild_name=server_config.guild_name,
                    ban_results=ban_results
                )
            else:
                logger.info(f"ChatGPT determined message from {username} ({user_id}) is not a scam")
                
        except Exception as e:
            logger.error(f"Error handling AutoMod event: {e}")
            # Don't re-raise - continue processing other events
    
    def create_bot(self, token: str) -> commands.Bot:
        """Create and configure the Discord bot."""
        intents = nextcord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True
        
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        @bot.event
        async def on_ready():
            logger.info(f"Bot is online as {bot.user}")
            logger.info(f"Monitoring {len(self.servers)} servers")
            
            # Verify bot has access to all configured servers
            for guild_id, server_config in self.servers.items():
                guild = bot.get_guild(guild_id)
                if guild:
                    logger.info(f"✅ Connected to {guild.name} ({guild_id})")
                    
                    # Check bot permissions
                    if bot.user:
                        bot_member = guild.get_member(bot.user.id)
                        if bot_member and bot_member.guild_permissions.ban_members:
                            logger.info(f"✅ Has ban permissions in {guild.name}")
                        else:
                            logger.warning(f"⚠️  Missing ban permissions in {guild.name}")
                else:
                    logger.warning(f"❌ Cannot access server {server_config.guild_name} ({guild_id})")
        
        @bot.event
        async def on_auto_moderation_action_execution(payload: nextcord.AutoModerationActionExecution):
            await self.handle_automod_event(payload)
            
        @bot.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"Bot error in event {event}: {args}")

        # Add ban/unban commands
        @bot.command(name='mban')
        async def mass_ban_command(ctx, user_id: str, *, notes: str = "No notes provided"):
            """Mass ban a user from all servers. Usage: ?mban <user_id> <notes>"""
            # Check if user is authorized
            if not self.is_authorized_user(ctx.author.id):
                await ctx.send("❌ You are not authorized to use this command.")
                return
            
            # Validate user ID
            try:
                target_user_id = int(user_id)
            except ValueError:
                await ctx.send("❌ Invalid user ID format. Please provide a valid Discord user ID.")
                return
            
            # Prevent self-bans
            if target_user_id == ctx.author.id:
                await ctx.send("❌ You cannot ban yourself.")
                return
            
            # Prevent banning authorized users
            if self.is_authorized_user(target_user_id):
                await ctx.send("❌ You cannot ban an authorized user.")
                return
            
            await ctx.send(f"⏳ Mass banning user {target_user_id} from all servers...")
            
            # Get configured server name
            server_config = self.servers.get(ctx.guild.id)
            originating_server_name = server_config.guild_name if server_config else ctx.guild.name
            
            # Execute mass ban
            ban_results = await self.mass_ban_user(
                target_user_id, 
                f"Mass ban by {ctx.author.display_name}: {notes}",
                ctx.author.id,
                ctx.author.display_name,
                originating_server_name
            )
            
            # Report results
            successful_bans = sum(1 for success in ban_results.values() if success)
            total_servers = len(ban_results)
            
            if successful_bans == total_servers:
                await ctx.send(f"✅ Successfully banned user {target_user_id} from all {total_servers} servers.")
            elif successful_bans > 0:
                await ctx.send(f"⚠️ Banned user {target_user_id} from {successful_bans}/{total_servers} servers. Check logs for details.")
            else:
                await ctx.send(f"❌ Failed to ban user {target_user_id} from any servers. Check logs for details.")

        @bot.command(name='munban')
        async def mass_unban_command(ctx, user_id: str, *, notes: str = "No notes provided"):
            """Mass unban a user from all servers. Usage: ?munban <user_id> <notes>"""
            # Check if user is authorized
            if not self.is_authorized_user(ctx.author.id):
                await ctx.send("❌ You are not authorized to use this command.")
                return
            
            # Validate user ID
            try:
                target_user_id = int(user_id)
            except ValueError:
                await ctx.send("❌ Invalid user ID format. Please provide a valid Discord user ID.")
                return
            
            await ctx.send(f"⏳ Mass unbanning user {target_user_id} from all servers...")
            
            # Get configured server name
            server_config = self.servers.get(ctx.guild.id)
            originating_server_name = server_config.guild_name if server_config else ctx.guild.name
            
            # Execute mass unban
            unban_results = await self.mass_unban_user(
                target_user_id, 
                f"Mass unban by {ctx.author.display_name}: {notes}",
                ctx.author.id,
                ctx.author.display_name,
                originating_server_name
            )
            
            # Report results
            successful_unbans = sum(1 for success in unban_results.values() if success)
            total_servers = len(unban_results)
            
            if successful_unbans == total_servers:
                await ctx.send(f"✅ Successfully unbanned user {target_user_id} from all {total_servers} servers.")
            elif successful_unbans > 0:
                await ctx.send(f"⚠️ Unbanned user {target_user_id} from {successful_unbans}/{total_servers} servers. Check logs for details.")
            else:
                await ctx.send(f"❌ Failed to unban user {target_user_id} from any servers. Check logs for details.")

        @bot.command(name='ban')
        async def ban_command(ctx, user_id: str, *, notes: str = "No notes provided"):
            """Ban a user from the current server. Usage: ?ban <user_id> <notes>"""
            # Check if user is authorized
            if not self.is_authorized_user(ctx.author.id):
                await ctx.send("❌ You are not authorized to use this command.")
                return
            
            # Validate user ID
            try:
                target_user_id = int(user_id)
            except ValueError:
                await ctx.send("❌ Invalid user ID format. Please provide a valid Discord user ID.")
                return
            
            # Prevent self-bans
            if target_user_id == ctx.author.id:
                await ctx.send("❌ You cannot ban yourself.")
                return
            
            # Prevent banning authorized users
            if self.is_authorized_user(target_user_id):
                await ctx.send("❌ You cannot ban an authorized user.")
                return
            
            # Get configured server name
            server_config = self.servers.get(ctx.guild.id)
            server_display_name = server_config.guild_name if server_config else ctx.guild.name
            
            await ctx.send(f"⏳ Banning user {target_user_id} from {server_display_name}...")
            
            # Execute single server ban
            success = await self.single_ban_user(
                target_user_id,
                ctx.guild,
                f"Ban by {ctx.author.display_name}: {notes}",
                ctx.author.id,
                ctx.author.display_name
            )
            
            if success:
                await ctx.send(f"✅ Successfully banned user {target_user_id} from {server_display_name}.")
            else:
                await ctx.send(f"❌ Failed to ban user {target_user_id} from {server_display_name}. Check logs for details.")

        @bot.command(name='unban')
        async def unban_command(ctx, user_id: str, *, notes: str = "No notes provided"):
            """Unban a user from the current server. Usage: ?unban <user_id> <notes>"""
            # Check if user is authorized
            if not self.is_authorized_user(ctx.author.id):
                await ctx.send("❌ You are not authorized to use this command.")
                return
            
            # Validate user ID
            try:
                target_user_id = int(user_id)
            except ValueError:
                await ctx.send("❌ Invalid user ID format. Please provide a valid Discord user ID.")
                return
            
            # Get configured server name
            server_config = self.servers.get(ctx.guild.id)
            server_display_name = server_config.guild_name if server_config else ctx.guild.name
            
            await ctx.send(f"⏳ Unbanning user {target_user_id} from {server_display_name}...")
            
            # Execute single server unban
            success = await self.single_unban_user(
                target_user_id,
                ctx.guild,
                f"Unban by {ctx.author.display_name}: {notes}",
                ctx.author.id,
                ctx.author.display_name
            )
            
            if success:
                await ctx.send(f"✅ Successfully unbanned user {target_user_id} from {server_display_name}.")
            else:
                await ctx.send(f"❌ Failed to unban user {target_user_id} from {server_display_name}. Check logs for details.")
        
        return bot

    async def setup_session(self):
        """Setup HTTP session with connection pooling and webhook queue."""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'BadBot-AutoMod/1.0'}
        )
        logger.info("HTTP session initialized with connection pooling")
        
        # Initialize webhook queue
        self.webhook_queue = WebhookQueue(self.session, self.webhook_rate_limiter)
        logger.info("Webhook queue initialized")

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        
        # Stop webhook queue processing
        if self.webhook_queue:
            await self.webhook_queue.stop_processing()
            logger.info(f"Final webhook queue size: {self.webhook_queue.get_queue_size()}")
        
        if self.session:
            await self.session.close()
        if self.bot:
            await self.bot.close()
        logger.info("Cleanup completed")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()

    async def run(self) -> None:
        """Run the bot with graceful shutdown."""
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # Load configuration
            self.load_config()
            token = self.load_credentials()
            
            # Setup HTTP session
            await self.setup_session()
            
            # Create and run bot
            self.bot = self.create_bot(token)
            
            # Run bot until shutdown signal
            bot_task = asyncio.create_task(self.bot.start(token))
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Graceful shutdown
            logger.info("Initiating graceful shutdown...")
            await self.cleanup()
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            await self.cleanup()
            raise

async def main():
    """Main entry point."""
    bot = BadBotAutoMod()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main()) 
