"""
Discord AutoMod Bot for Multi-Server Scam Detection and Banning

This bot monitors AutoMod events across multiple Discord servers and uses GPT-4
to detect scam messages. When a scam is detected, the user is banned from all
configured servers and notifications are sent to webhooks.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

import nextcord
from nextcord.ext import commands
import openai
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Configuration for a Discord server."""
    guild_id: int
    guild_name: str
    log_channel_id: int

@dataclass
class WebhookConfig:
    """Configuration for webhook notifications."""
    url: str
    name: str
    server_name: Optional[str] = None

class BadBotAutoMod:
    """Main bot class for handling AutoMod events and scam detection."""
    
    def __init__(self):
        self.bot: Optional[commands.Bot] = None
        self.badbot_servers_automod: Dict[int, ServerConfig] = {}
        self.webhook_urls: List[WebhookConfig] = []
        self.banned_users: Set[int] = set()  # Track banned users to prevent duplicate processing
        
    def load_config(self) -> None:
        """Load configuration from environment variables."""
        try:
            # Load server configurations from environment variable
            servers_env = os.environ.get("badbot_automod_servers")
            if not servers_env:
                logger.error("Environment variable 'badbot_automod_servers' not found")
                raise ValueError("badbot_automod_servers environment variable is required")
                
            # Parse servers in format: guildID:guildName:logChannelID,guildID2:guildName2:logChannelID2
            server_pairs = servers_env.split(',')
            
            for pair in server_pairs:
                if ':' in pair:
                    parts = pair.strip().split(':')
                    if len(parts) == 3:
                        guild_id_str, guild_name, log_channel_id_str = parts
                        try:
                            guild_id = int(guild_id_str.strip())
                            log_channel_id = int(log_channel_id_str.strip())
                            
                            server_config = ServerConfig(
                                guild_id=guild_id,
                                guild_name=guild_name.strip(),
                                log_channel_id=log_channel_id
                            )
                            self.badbot_servers_automod[guild_id] = server_config
                            logger.info(f"Loaded server: {guild_name} ({guild_id}) with log channel {log_channel_id}")
                        except ValueError:
                            logger.warning(f"Invalid server ID or log channel ID format: {pair}")
                            continue
                    else:
                        logger.warning(f"Invalid server format (expected guildID:guildName:logChannelID): {pair}")
                        continue
                        
            logger.info(f"Loaded {len(self.badbot_servers_automod)} servers from environment")
            
            # Load webhook URLs from environment variable
            webhooks_env = os.environ.get("badbot_automod_webhookurls")
            if webhooks_env:
                # Parse webhooks in format: webhook1:servername1,webhook2:servername2,webhook3
                webhook_pairs = webhooks_env.split(',')
                
                for i, webhook_pair in enumerate(webhook_pairs):
                    webhook_pair = webhook_pair.strip()
                    if webhook_pair:
                        # Check if webhook has server name (format: webhookURL:servername)
                        if ':' in webhook_pair:
                            parts = webhook_pair.split(':', 1)
                            webhook_url = parts[0].strip()
                            server_name = parts[1].strip()
                            webhook_config = WebhookConfig(
                                url=webhook_url,
                                name=f"Webhook {i+1} ({server_name})",
                                server_name=server_name
                            )
                            logger.info(f"Loaded webhook {i+1} for server '{server_name}': {webhook_url[:50]}...")
                        else:
                            # Legacy format: just webhook URL
                            webhook_config = WebhookConfig(
                                url=webhook_pair,
                                name=f"Webhook {i+1}",
                                server_name=None
                            )
                            logger.info(f"Loaded webhook {i+1}: {webhook_pair[:50]}...")
                        
                        self.webhook_urls.append(webhook_config)
                        
                logger.info(f"Loaded {len(self.webhook_urls)} webhooks from environment")
            else:
                logger.warning("No webhooks configured - notifications will be disabled")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
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
            openai_apikey = os.environ.get("badbot_openai_key")
            if not openai_apikey:
                logger.error("Environment variable 'badbot_openai_key' not found")
                raise ValueError("badbot_openai_key environment variable is required")
                
            # Set OpenAI API key
            openai.api_key = openai_apikey
            logger.info("Successfully loaded credentials from environment variables")
            
            return badbot_discord_token
            
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            raise
    
    async def check_gpt_for_scam(self, content: str) -> bool:
        """
        Check if the given content is a scam using GPT-4.
        
        Args:
            content: The message content to analyze
            
        Returns:
            True if GPT-4 determines it's a scam, False otherwise
        """
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
            f"\"{content}\"\n\n"
            "Is this message a scam? Start your answer with 'YES:' or 'NO:'."
        )

        try:
            # Get OpenAI model and temperature from environment variables
            openai_model = os.environ.get("openai_model", "gpt-4o-mini")
            openai_temp = float(os.environ.get("openai_temperature", "0.0"))
            
            response = openai.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,
                temperature=openai_temp
            )
            ai_reply = response.choices[0].message.content.strip()
            logger.info(f"GPT-4 reply: {ai_reply}")
            
            return ai_reply.lower().startswith("yes:")
            
        except Exception as e:
            logger.error(f"Error during GPT-4 check: {e}")
            return False
    
    async def ban_user_from_all_servers(self, user_id: int, reason: str) -> Dict[int, bool]:
        """
        Ban a user from all configured servers.
        
        Args:
            user_id: The Discord user ID to ban
            reason: The reason for the ban
            
        Returns:
            Dictionary mapping guild_id to success status
        """
        ban_results = {}
        
        for guild_id, server_config in self.badbot_servers_automod.items():
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Could not find guild {guild_id}")
                    ban_results[guild_id] = False
                    continue
                
                # Check if user is in the guild
                member = guild.get_member(user_id)
                if not member:
                    logger.info(f"User {user_id} not found in guild {guild.name} ({guild_id})")
                    ban_results[guild_id] = True  # Consider it successful if user not in guild
                    continue
                
                # Ban the user
                await guild.ban(member, reason=reason)
                logger.info(f"Successfully banned user {user_id} from {guild.name} ({guild_id})")
                ban_results[guild_id] = True
                
                # Wait 2 seconds before next ban
                await asyncio.sleep(2)
                
            except nextcord.Forbidden:
                logger.error(f"Bot lacks permission to ban in guild {guild_id}")
                ban_results[guild_id] = False
            except nextcord.HTTPException as e:
                logger.error(f"HTTP error banning user {user_id} from guild {guild_id}: {e}")
                ban_results[guild_id] = False
            except Exception as e:
                logger.error(f"Unexpected error banning user {user_id} from guild {guild_id}: {e}")
                ban_results[guild_id] = False
        
        return ban_results
    
    async def send_webhook_notifications(self, user_id: int, username: str, 
                                       message_content: str, source_guild_name: str,
                                       source_guild_id: int, ban_results: Dict[int, bool]) -> None:
        """
        Send notifications to configured webhooks.
        
        Args:
            user_id: The banned user's ID
            username: The banned user's username
            message_content: The message that triggered the ban
            source_guild_name: Name of the guild where the message was posted
            source_guild_id: ID of the guild where the message was posted
            ban_results: Results of ban attempts across all servers
        """
        if not self.webhook_urls:
            logger.info("No webhooks configured, skipping notifications")
            return
        
        # Prepare webhook payload
        embed = nextcord.Embed(
            title="🚨 Scammer Detected and Banned",
            description=f"A user has been banned across all monitored servers for posting scam content.",
            color=0xFF0000,
            timestamp=nextcord.utils.utcnow()
        )
        
        embed.add_field(
            name="👤 User Information",
            value=f"**Username:** {username}\n**User ID:** {user_id}",
            inline=False
        )
        
        embed.add_field(
            name="📝 Scam Message",
            value=f"```{message_content[:1000]}```",
            inline=False
        )
        
        embed.add_field(
            name="🏠 Source Server",
            value=f"**Name:** {source_guild_name}\n**ID:** {source_guild_id}",
            inline=True
        )
        
        # Add ban results
        successful_bans = sum(1 for success in ban_results.values() if success)
        total_servers = len(ban_results)
        
        embed.add_field(
            name="🔨 Ban Results",
            value=f"Successfully banned from {successful_bans}/{total_servers} servers",
            inline=True
        )
        
        embed.set_footer(text="BadBot AutoMod System")
        
        # Send to webhooks - prioritize server-specific webhooks
        async with aiohttp.ClientSession() as session:
            # First, try to send to server-specific webhooks
            server_specific_sent = False
            for webhook_config in self.webhook_urls:
                if webhook_config.server_name and webhook_config.server_name.lower() == source_guild_name.lower():
                    try:
                        webhook = nextcord.Webhook.from_url(webhook_config.url, session=session)
                        await webhook.send(embed=embed)
                        logger.info(f"Sent server-specific webhook notification to {webhook_config.name}")
                        server_specific_sent = True
                        
                        # Wait 2 seconds between webhook posts
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Failed to send server-specific webhook to {webhook_config.name}: {e}")
            
            # If no server-specific webhook was found or sent, send to general webhooks
            if not server_specific_sent:
                for webhook_config in self.webhook_urls:
                    if not webhook_config.server_name:  # Only general webhooks
                        try:
                            webhook = nextcord.Webhook.from_url(webhook_config.url, session=session)
                            await webhook.send(embed=embed)
                            logger.info(f"Sent general webhook notification to {webhook_config.name}")
                            
                            # Wait 2 seconds between webhook posts
                            await asyncio.sleep(2)
                            
                        except Exception as e:
                            logger.error(f"Failed to send general webhook to {webhook_config.name}: {e}")
    
    async def handle_automod_event(self, payload: nextcord.AutoModerationActionExecution) -> None:
        """
        Handle AutoMod events and process scam detection.
        
        Args:
            payload: The AutoMod event payload
        """
        logger.info(f"Received AutoMod event from guild {payload.guild_id}")
        
        # Only process message blocking events
        if payload.action.type != nextcord.AutoModerationActionType.block_message:
            logger.debug("Ignoring non-block_message AutoMod action")
            return
        
        # Check if this guild is in our monitoring list
        if payload.guild_id not in self.badbot_servers_automod:
            logger.debug(f"Guild {payload.guild_id} not in monitoring list")
            return
        
        # Extract user information
        user_id = payload.member_id
        if not user_id:
            logger.warning("No user ID in AutoMod payload")
            return
        
        # Check if we've already processed this user
        if user_id in self.banned_users:
            logger.info(f"User {user_id} already processed, skipping")
            return
        
        # Get guild information
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.error(f"Could not fetch guild {payload.guild_id}")
            return
        
        # Get user information
        member = guild.get_member(user_id)
        username = member.display_name if member else f"User {user_id}"
        
        # Extract blocked content
        blocked_content = payload.content or payload.matched_keyword or ""
        if not blocked_content.strip():
            logger.info("No content to analyze, skipping")
            return
        
        logger.info(f"Analyzing content from user {username} ({user_id})")
        
        # Check with GPT-4
        is_scam = await self.check_gpt_for_scam(blocked_content)
        
        if is_scam:
            logger.info(f"GPT-4 confirmed scam from user {username} ({user_id})")
            
            # Mark user as processed
            self.banned_users.add(user_id)
            
            # Ban from all servers
            ban_results = await self.ban_user_from_all_servers(
                user_id, 
                f"Scam detected by GPT-4. Original message: {blocked_content[:100]}..."
            )
            
            # Send webhook notifications
            await self.send_webhook_notifications(
                user_id=user_id,
                username=username,
                message_content=blocked_content,
                source_guild_name=guild.name,
                source_guild_id=guild.id,
                ban_results=ban_results
            )
            
            # Log to the source server's log channel
            server_config = self.badbot_servers_automod[payload.guild_id]
            log_channel = self.bot.get_channel(server_config.log_channel_id)
            
            if log_channel:
                embed = nextcord.Embed(
                    title="🚨 Scammer Banned",
                    description=f"User {member.mention if member else f'({user_id})'} has been banned from all monitored servers.",
                    color=0xFF0000
                )
                embed.add_field(name="Scam Message", value=f"```{blocked_content}```", inline=False)
                embed.add_field(name="Ban Results", value=f"Banned from {sum(ban_results.values())}/{len(ban_results)} servers", inline=True)
                
                await log_channel.send(embed=embed)
        else:
            logger.info(f"GPT-4 determined message from {username} ({user_id}) is not a scam")
            
            # Log non-scam to the source server's log channel
            server_config = self.badbot_servers_automod[payload.guild_id]
            log_channel = self.bot.get_channel(server_config.log_channel_id)
            
            if log_channel:
                embed = nextcord.Embed(
                    title="✅ Message Analyzed",
                    description=f"Message from {member.mention if member else f'({user_id})'} was flagged by AutoMod but determined to be safe.",
                    color=0x00FF00
                )
                embed.add_field(name="Message Content", value=f"```{blocked_content}```", inline=False)
                
                await log_channel.send(embed=embed)
    
    def create_bot(self, token: str) -> commands.Bot:
        """
        Create and configure the Discord bot.
        
        Args:
            token: Discord bot token
            
        Returns:
            Configured Discord bot instance
        """
        intents = nextcord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True
        
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        @bot.event
        async def on_ready():
            logger.info(f"Bot is online as {bot.user}")
            logger.info(f"Monitoring {len(self.badbot_servers_automod)} servers")
            
            # Verify bot has access to all configured servers
            for guild_id, server_config in self.badbot_servers_automod.items():
                guild = bot.get_guild(guild_id)
                if guild:
                    logger.info(f"✅ Connected to {guild.name} ({guild_id})")
                else:
                    logger.warning(f"❌ Cannot access server {server_config.guild_name} ({guild_id})")
        
        @bot.event
        async def on_auto_moderation_action_execution(payload: nextcord.AutoModerationActionExecution):
            await self.handle_automod_event(payload)
        
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