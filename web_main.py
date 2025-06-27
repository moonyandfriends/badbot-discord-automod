#!/usr/bin/env python3
"""
Web server version of the Discord bot for Railway deployment.
This includes a health check endpoint that Railway can use.
"""

import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn

from main import BadBotAutoMod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BadBot Discord AutoMod", version="1.0.0")

# Global bot instance
bot_instance = None

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "BadBot Discord AutoMod is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    try:
        # Check environment variables
        required_vars = [
            "badbot_discord_token",
            "badbot_openai_key", 
            "badbot_automod_servers"
        ]
        
        missing = []
        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            raise HTTPException(status_code=500, detail=f"Missing environment variables: {', '.join(missing)}")
        
        # Test bot configuration
        bot = BadBotAutoMod()
        bot.load_config()
        bot.load_credentials()
        
        return {"status": "healthy", "servers": len(bot.badbot_servers_automod), "webhooks": len(bot.webhook_urls)}
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start")
async def start_bot():
    """Start the Discord bot."""
    global bot_instance
    
    try:
        if bot_instance:
            return {"message": "Bot is already running"}
        
        # Create and start bot
        bot = BadBotAutoMod()
        bot.load_config()
        token = bot.load_credentials()
        
        # Start bot in background
        bot_instance = bot
        asyncio.create_task(bot.run())
        
        return {"message": "Bot started successfully"}
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_bot():
    """Stop the Discord bot."""
    global bot_instance
    
    try:
        if bot_instance and bot_instance.bot:
            await bot_instance.bot.close()
            bot_instance = None
            return {"message": "Bot stopped successfully"}
        else:
            return {"message": "Bot is not running"}
            
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def bot_status():
    """Get bot status."""
    global bot_instance
    
    if bot_instance and bot_instance.bot and bot_instance.bot.is_ready():
        return {
            "status": "running",
            "user": str(bot_instance.bot.user),
            "servers": len(bot_instance.badbot_servers_automod)
        }
    else:
        return {"status": "stopped"}

if __name__ == "__main__":
    # Start the web server
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 