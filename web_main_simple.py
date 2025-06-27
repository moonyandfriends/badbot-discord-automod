#!/usr/bin/env python3
"""
Simplified web server version of the Discord bot for Railway deployment.
This version avoids importing the bot immediately to prevent hanging.
"""

import os
import logging
from fastapi import FastAPI, HTTPException
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BadBot Discord AutoMod", version="1.0.0")

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
            "badbot_automod_servers",
            "badbot_automod_webhookurls"
        ]
        
        missing = []
        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            return {"status": "unhealthy", "missing_vars": missing}
        
        # Count servers and webhooks
        servers_env = os.environ.get("badbot_automod_servers", "")
        webhooks_env = os.environ.get("badbot_automod_webhookurls", "")
        
        server_count = len([s for s in servers_env.split(',') if '|' in s]) if servers_env else 0
        webhook_count = len([w for w in webhooks_env.split(',') if w.strip()]) if webhooks_env else 0
        
        return {
            "status": "healthy", 
            "servers": server_count, 
            "webhooks": webhook_count,
            "message": "Environment variables configured correctly"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/test")
async def test_imports():
    """Test importing the bot modules."""
    try:
        # Test basic imports
        import nextcord
        import openai
        import aiohttp
        
        # Test our bot import
        from main import BadBotAutoMod
        
        return {"status": "success", "message": "All imports working"}
        
    except Exception as e:
        logger.error(f"Import test failed: {e}")
        return {"status": "failed", "error": str(e)}

@app.post("/start")
async def start_bot():
    """Start the Discord bot."""
    try:
        # Import and start bot
        from main import BadBotAutoMod
        import asyncio
        
        bot = BadBotAutoMod()
        bot.load_config()
        token = bot.load_credentials()
        
        # Start bot in background
        asyncio.create_task(bot.run())
        
        return {"message": "Bot started successfully"}
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Start the web server
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting web server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 