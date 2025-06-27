#!/usr/bin/env python3
"""
Simple health check for Railway deployment.
"""

import os
import sys

def check_health():
    """Check if the bot can start up properly."""
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
            print(f"Missing environment variables: {', '.join(missing)}")
            return False
        
        # Try to import main module
        from main import BadBotAutoMod
        
        # Create bot instance
        bot = BadBotAutoMod()
        
        # Load configuration
        bot.load_config()
        
        # Load credentials
        bot.load_credentials()
        
        print("Health check passed!")
        return True
        
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1) 