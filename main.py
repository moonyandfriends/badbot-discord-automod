#!/usr/bin/env python3
"""
Discord AutoMod Bot for Railway
Monitors AutoMod events, uses ChatGPT to detect scams, bans users across all servers, and sends webhook notifications.
"""

import os
import asyncio
import logging
import aiohttp
from typing import Dict, List
from dataclasses import dataclass

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
                    
        logger.info(f"Loaded {len(self.servers)} servers from environment")
        
        # Load webhook URLs
        webhooks_env = os.environ.get("badbot_automod_webhookurls")
        if not webhooks_env:
            raise ValueError("badbot_automod_webhookurls environment variable is required")
            
        self.webhook_urls = [url.strip() for url in webhooks_env.split(',') if url.strip()]
        logger.info(f"Loaded {len(self.webhook_urls)} webhook URLs")
        
    def load_credentials(self) -> str:
        """Load Discord token and OpenAI key from environment variables."""
        logger.info("Loading credentials...")
        
        # Load Discord token
        discord_token = os.environ.get("badbot_discord_token")
        if not discord_token:
            raise ValueError("badbot_discord_token environment variable is required")
            
        # Load OpenAI key
        openai_key = os.environ.get("badbot_openai_key")
        if not openai_key:
            raise ValueError("badbot_openai_key environment variable is required")
            
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_key)
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
            f"\"{content}\"\n\n"
            "Is this message a scam? Start your answer with 'YES:' or 'NO:'."
        )

        try:
            logger.info("Sending content to ChatGPT for analysis...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,
                temperature=0.0
            )
            ai_reply = response.choices[0].message.content.strip()
            logger.info(f"ChatGPT response: {ai_reply}")
            
            return ai_reply.lower().startswith("yes:")
            
        except Exception as e:
            logger.error(f"Error checking content with ChatGPT: {e}")
            return False
            
    async def ban_user_from_all_servers(self, user_id: int, reason: str) -> Dict[int, bool]:
        """Ban user from all configured servers."""
        ban_results = {}
        
        for guild_id, server_config in self.servers.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Could not find guild {server_config.guild_name} ({guild_id})")
                ban_results[guild_id] = False
                continue
                
            try:
                # Get member object
                member = guild.get_member(user_id)
                if member:
                    await guild.ban(member, reason=reason)
                    logger.info(f"Banned user {user_id} from {server_config.guild_name}")
                    ban_results[guild_id] = True
                else:
                    # User not in this server
                    logger.info(f"User {user_id} not found in {server_config.guild_name}")
                    ban_results[guild_id] = False
                    
                # Add delay between bans to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to ban user {user_id} from {server_config.guild_name}: {e}")
                ban_results[guild_id] = False
                
        return ban_results
        
    async def send_webhook_notifications(self, user_id: int, username: str, 
                                       message_content: str, source_guild_name: str,
                                       ban_results: Dict[int, bool]) -> None:
        """Send notifications to all configured webhooks."""
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
        
        # Send to all webhooks
        async with aiohttp.ClientSession() as session:
            for webhook_url in self.webhook_urls:
                try:
                    webhook_data = {
                        "username": "BadBot AutoMod",
                        "embeds": [embed_data]
                    }
                    
                    async with session.post(webhook_url, json=webhook_data) as response:
                        if response.status == 204:
                            logger.info("Webhook notification sent successfully")
                        else:
                            logger.warning(f"Webhook returned status {response.status}")
                            
                    # Add delay between webhook posts
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Failed to send webhook notification: {e}")
                    
    async def handle_automod_event(self, payload: nextcord.AutoModerationActionExecution) -> None:
        """Handle AutoMod action execution events."""
        logger.info("Received AutoMod event")
        
        # Only process message blocks
        if payload.action.type != nextcord.AutoModerationActionType.block_message:
            logger.info("Action is not block_message, ignoring")
            return
            
        # Check if this is from one of our monitored servers
        guild_id = payload.guild_id
        if guild_id not in self.servers:
            logger.info(f"Event from unmonitored server {guild_id}, ignoring")
            return
            
        server_config = self.servers[guild_id]
        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            logger.warning(f"Could not find guild {guild_id}")
            return
            
        logger.info(f"Processing AutoMod event from {server_config.guild_name}")
        
        # Get user information
        user_id = payload.member_id
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