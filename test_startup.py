#!/usr/bin/env python3
"""
Simple startup test for the Discord bot.
This script tests basic imports and configuration loading.
"""

import os
import sys

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import nextcord
        print("✅ nextcord imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import nextcord: {e}")
        return False
    
    try:
        import openai
        print("✅ openai imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import openai: {e}")
        return False
    
    try:
        import aiohttp
        print("✅ aiohttp imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import aiohttp: {e}")
        return False
    
    return True

def test_environment_variables():
    """Test if required environment variables are set."""
    print("\nTesting environment variables...")
    
    required_vars = [
        "badbot_discord_token",
        "badbot_openai_key", 
        "badbot_automod_servers"
    ]
    
    missing_vars = []
    for var in required_vars:
        if os.environ.get(var):
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\nMissing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def test_config_parsing():
    """Test configuration parsing."""
    print("\nTesting configuration parsing...")
    
    try:
        from main import BadBotAutoMod
        
        bot = BadBotAutoMod()
        bot.load_config()
        print("✅ Configuration loaded successfully")
        print(f"   Servers loaded: {len(bot.badbot_servers_automod)}")
        print(f"   Webhooks loaded: {len(bot.webhook_urls)}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Discord Bot Startup Test")
    print("=" * 40)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import test failed")
        sys.exit(1)
    
    # Test environment variables
    if not test_environment_variables():
        print("\n❌ Environment variable test failed")
        sys.exit(1)
    
    # Test configuration parsing
    if not test_config_parsing():
        print("\n❌ Configuration parsing test failed")
        sys.exit(1)
    
    print("\n✅ All tests passed! Bot should start successfully.")

if __name__ == "__main__":
    main() 