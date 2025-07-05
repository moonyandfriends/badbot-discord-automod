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
            
            # Wait 2 seconds before processing next webhook
            logger.info("Waiting 2 seconds before processing next webhook...")
            await asyncio.sleep(2)
        
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
            "are highly suspicious. If the content contains any of these elements or seems to fit "
            "the pattern of scam behavior, consider it a scam."
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
