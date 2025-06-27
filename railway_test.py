#!/usr/bin/env python3
"""
Minimal test script for Railway to identify import issues.
This will help us figure out exactly where the Docker build is hanging.
"""

import sys
import os
import time

def log(message):
    """Log with timestamp."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()  # Force output immediately

def main():
    """Main test function."""
    log("🚀 Railway Import Test Starting")
    log(f"Python version: {sys.version}")
    log(f"Platform: {sys.platform}")
    
    # Test 1: Basic Python imports
    log("Testing basic Python imports...")
    try:
        import json
        log("✅ json imported")
        
        import asyncio
        log("✅ asyncio imported")
        
        import logging
        log("✅ logging imported")
    except Exception as e:
        log(f"❌ Basic imports failed: {e}")
        return 1
    
    # Test 2: Requirements imports one by one
    log("Testing requirements.txt imports...")
    
    try:
        log("Testing nextcord...")
        import nextcord
        log("✅ nextcord imported")
    except Exception as e:
        log(f"❌ nextcord failed: {e}")
        return 1
    
    try:
        log("Testing openai...")
        import openai
        log("✅ openai imported")
    except Exception as e:
        log(f"❌ openai failed: {e}")
        return 1
    
    try:
        log("Testing aiohttp...")
        import aiohttp
        log("✅ aiohttp imported")
    except Exception as e:
        log(f"❌ aiohttp failed: {e}")
        return 1
    
    try:
        log("Testing fastapi...")
        import fastapi
        log("✅ fastapi imported")
    except Exception as e:
        log(f"❌ fastapi failed: {e}")
        return 1
    
    try:
        log("Testing uvicorn...")
        import uvicorn
        log("✅ uvicorn imported")
    except Exception as e:
        log(f"❌ uvicorn failed: {e}")
        return 1
    
    # Test 3: Our bot imports
    log("Testing bot imports...")
    try:
        log("Importing main.py...")
        import main
        log("✅ main.py imported")
        
        log("Creating bot instance...")
        bot = main.BadBotAutoMod()
        log("✅ BadBotAutoMod instance created")
        
        log("Loading config...")
        bot.load_config()
        log("✅ Config loaded")
        
    except Exception as e:
        log(f"❌ Bot imports failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 4: Environment variables
    log("Testing environment variables...")
    required_vars = ["badbot_discord_token", "badbot_openai_key", "badbot_automod_servers", "badbot_automod_webhookurls"]
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            log(f"✅ {var}: Set ({len(str(value))} chars)")
        else:
            log(f"❌ {var}: Missing")
    
    log("🎉 All tests completed successfully!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    log(f"Test completed with exit code: {exit_code}")
    sys.exit(exit_code) 