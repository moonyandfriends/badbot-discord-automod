#!/usr/bin/env python3
"""
Discord AutoMod Bot for Railway - Improved Version
Monitors AutoMod events, uses ChatGPT to detect scams, bans users across all servers, and sends webhook notifications.
"""

import os
import asyncio
import logging
import aiohttp
import re
from typing import Dict, List, Set
from dataclasses import dataclass
from urllib.parse import urlparse

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

class BadBotAutoMod:
    """Discord AutoMod bot that detects scams and bans users across multiple servers."""
    
    def __init__(self):
        self.bot = None
        self.servers: Dict[int, ServerConfig] = {}
        self.webhook_urls: List[str] = []
        self.openai_client = None
        self.processed_users: Set[int] = set()  # Prevent duplicate processing
        self.openai_model = "gpt-4o-mini"  # Default model
        
    def validate_webhook_url(self, url: str) -> bool:
        """Validate that a webhook URL is properly formatted."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['http', 'https'] and
                'discord.com' in parsed.netloc and
                '/api/webhooks/' in parsed.path
            )
        except Exception:
            return False
        
    def load_config(self) -> None:
<<<<<<< HEAD
        """Load configuration from environment variables and config.json file."""
        try:
            # Load server configurations from config.json
            with open("config.json", "r") as f:
                config = json.load(f)
                
            # Load server configurations
            for server_data in config.get("servers", []):
                server_config = ServerConfig(
                    guild_id=server_data["guild_id"],
                    guild_name=server_data["guild_name"],
                    log_channel_id=server_data["log_channel_id"]
                )
                self.badbot_servers_automod[server_config.guild_id] = server_config
                
            logger.info(f"Loaded {len(self.badbot_servers_automod)} servers from config.json")
            
        except FileNotFoundError:
            logger.error("config.json not found. Please create it with proper configuration.")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config.json: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required key in config.json: {e}")
            raise
    
    def load_credentials(self) -> str:
        """Load Discord token and OpenAI API key from environment variables."""
        try:
            # Load Discord token from environment variable
            badbot_discord_token = os.environ.get("badbot_discord_token")
            if not badbot_discord_token:
                logger.error("Environment variable 'badbot_discord_token' not found")
                raise ValueError("badbot_discord_token environment variable is required")
                
            # Load OpenAI API key from environment variable
            openai_apikey = os.environ.get("openai_apikey")
            if not openai_apikey:
                logger.error("Environment variable 'openai_apikey' not found")
                raise ValueError("openai_apikey environment variable is required")
                
            # Set OpenAI API key
            openai.api_key = openai_apikey
            logger.info("Successfully loaded credentials from environment variables")
            
            return badbot_discord_token
            
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            raise
    
    def load_servers_from_env(self) -> None:
        """Load server configurations from environment variable."""
        try:
            servers_env = os.environ.get("servers")
            if not servers_env:
                logger.warning("Environment variable 'servers' not found, using config.json only")
                return
                
            # Parse servers in format: serverID1:servername1,serverID2:servername2
            server_pairs = servers_env.split(',')
            
            for pair in server_pairs:
                if ':' in pair:
                    server_id_str, server_name = pair.strip().split(':', 1)
                    try:
                        server_id = int(server_id_str.strip())
                        # Note: We still need log_channel_id from config.json
                        # This will be merged with config.json data
                        logger.info(f"Found server from env: {server_name} ({server_id})")
                    except ValueError:
                        logger.warning(f"Invalid server ID format: {server_id_str}")
                        continue
                        
            logger.info(f"Loaded {len(server_pairs)} server pairs from environment")
            
        except Exception as e:
            logger.error(f"Error loading servers from environment: {e}")
    
    def load_webhooks_from_env(self) -> None:
        """Load webhook URLs from environment variable."""
        try:
            webhooks_env = os.environ.get("badbot_automod_webhookurl")
            if not webhooks_env:
                logger.warning("Environment variable 'badbot_automod_webhookurl' not found, webhooks will be disabled")
                return
                
            # Parse webhooks in format: webhook1:webhook2:webhook3
            webhook_urls = webhooks_env.split(':')
            valid_webhooks = []
            
            for i, webhook_url in enumerate(webhook_urls):
                webhook_url = webhook_url.strip()
                if webhook_url:
                    # Validate webhook URL format - accept both discord.com and discordapp.com
                    if (webhook_url.startswith("https://discord.com/api/webhooks/") or 
                        webhook_url.startswith("https://discordapp.com/api/webhooks/")):
                        
                        # Convert discordapp.com to discord.com if needed
                        if webhook_url.startswith("https://discordapp.com/api/webhooks/"):
                            webhook_url = webhook_url.replace("discordapp.com", "discord.com")
                            logger.info(f"Converted discordapp.com URL to discord.com for webhook {i+1}")
                        
                        webhook_config = WebhookConfig(
                            url=webhook_url,
                            name=f"Webhook {i+1}"
                        )
                        self.webhook_urls.append(webhook_config)
                        valid_webhooks.append(webhook_url)
                        logger.info(f"Loaded webhook {i+1}: {webhook_url[:50]}...")
                    else:
                        logger.warning(f"Invalid webhook URL format: {webhook_url[:50]}...")
                        
            if not valid_webhooks:
                logger.warning("No valid webhook URLs found, webhooks will be disabled")
            else:
                logger.info(f"Loaded {len(valid_webhooks)} valid webhooks from environment")
            
        except Exception as e:
            logger.error(f"Error loading webhooks from environment: {e}")
            logger.warning("Webhooks will be disabled due to error")
    
    async def check_gpt_for_scam(self, content: str) -> bool:
        """
        Check if the given content is a scam using GPT-4.
=======
        """Load configuration from environment variables."""
        logger.info("Loading configuration from environment variables...")
>>>>>>> e047b6f37ad5b5bc5fd50b950866d4303aca3087
        
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
            raise ValueError("No valid webhook URLs found in badbot_automod_webhookurls")
            
        logger.info(f"Loaded {len(self.webhook_urls)} valid webhook URLs")
        
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
            self.openai_client = openai.OpenAI(api_key=openai_key)
            # Test the client with a simple request
            logger.info("Testing OpenAI client...")
            # Note: We don't actually make a test call here to avoid costs
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
            
        logger.info("Credentials loaded successfully")
        
        return discord_token
        
    async def check_gpt_for_scam(self, content: str) -> bool:
        """Check if content is a scam using ChatGPT."""
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
                temperature=0.0,
                timeout=30.0  # Add timeout
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
            return False
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking content with ChatGPT: {e}")
            return False
            
    async def ban_user_from_all_servers(self, user_id: int, reason: str) -> Dict[int, bool]:
        """Ban user from all configured servers with rate limiting."""
        ban_results = {}
        
        for guild_id, server_config in self.servers.items():
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
        """Send notifications to all configured webhooks with timeout."""
        successful_bans = sum(ban_results.values())
        total_servers = len(ban_results)
        
        # Create embed message
        embed_data = {
            "title": "🚨 Scammer Detected and Banned",
            "description": f"User **{username}** (ID: {user_id}) has been banned from {successful_bans}/{total_servers} servers.",
            "color": 0xFF0000,  # Red color
            "fields": [
                {
                    "name": "Source Server",
                    "value": source_guild_name,
                    "inline": True
                },
                {
                    "name": "Scam Message",
                    "value": f"```{message_content[:1000]}```",
                    "inline": False
                },
                {
                    "name": "Ban Results",
                    "value": f"Successfully banned from {successful_bans} out of {total_servers} servers",
                    "inline": True
                }
            ],
            "timestamp": nextcord.utils.utcnow().isoformat()
        }
        
        # Send to all webhooks with timeout
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i, webhook_url in enumerate(self.webhook_urls):
                try:
                    webhook_data = {
                        "username": "BadBot AutoMod",
                        "embeds": [embed_data]
                    }
                    
                    async with session.post(webhook_url, json=webhook_data) as response:
                        if response.status == 204:
                            logger.info(f"Webhook {i+1} notification sent successfully")
                        else:
                            logger.warning(f"Webhook {i+1} returned status {response.status}")
                            
                    # Rate limiting delay
                    await asyncio.sleep(1)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Webhook {i+1} request timed out")
                except Exception as e:
                    logger.error(f"Failed to send webhook {i+1} notification: {e}")
                    
    async def handle_automod_event(self, payload: nextcord.AutoModerationActionExecution) -> None:
        """Handle AutoMod action execution events."""
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
            self.processed_users.add(user_id)
            
            # Ban user from all servers
            ban_results = await self.ban_user_from_all_servers(user_id, "Scam detected by ChatGPT")
            
            # Send webhook notifications
            await self.send_webhook_notifications(
                user_id=user_id,
                username=username,
                message_content=blocked_content,
                source_guild_name=guild.name,
                ban_results=ban_results
            )
        else:
            logger.info(f"ChatGPT determined message from {username} ({user_id}) is not a scam")
    
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
    
    async def run(self) -> None:
        """Run the bot."""
        try:
            # Load configuration
            self.load_config()
            token = self.load_credentials()
            
            # Create and run bot
            self.bot = self.create_bot(token)
            await self.bot.start(token)
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

async def main():
    """Main entry point."""
    bot = BadBotAutoMod()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main()) 