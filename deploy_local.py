#!/usr/bin/env python3
"""
Local deployment test script for the Discord bot.
This script tests the bot locally before deploying to Railway.
"""

import os
import sys
import asyncio
from main import BadBotAutoMod

async def test_bot_startup():
    """Test if the bot can start up properly."""
    print("🚀 Testing Discord Bot Startup")
    print("=" * 40)
    
    try:
        # Create bot instance
        bot = BadBotAutoMod()
        
        # Test configuration loading
        print("📋 Loading configuration...")
        bot.load_config()
        print(f"   ✅ Loaded {len(bot.badbot_servers_automod)} servers")
        print(f"   ✅ Loaded {len(bot.webhook_urls)} webhooks")
        
        # Test credentials loading
        print("🔑 Loading credentials...")
        token = bot.load_credentials()
        print(f"   ✅ Discord token loaded")
        print(f"   ✅ OpenAI API key loaded")
        
        # Test bot creation (without starting)
        print("🤖 Creating bot instance...")
        bot_instance = bot.create_bot(token)
        print(f"   ✅ Bot instance created: {bot_instance.user if bot_instance.user else 'Not connected'}")
        
        print("\n✅ All tests passed! Bot is ready for deployment.")
        print("\n📝 Next steps:")
        print("1. Deploy to Railway (if not hanging)")
        print("2. Or deploy to Heroku: heroku create && git push heroku main")
        print("3. Or run locally: python main.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check environment variables are set")
        print("2. Verify Discord token is valid")
        print("3. Check OpenAI API key is valid")
        print("4. Verify server configuration format")
        return False

def check_environment():
    """Check if required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    required_vars = [
        "badbot_discord_token",
        "badbot_openai_key",
        "badbot_automod_servers"
    ]
    
    missing = []
    for var in required_vars:
        if os.environ.get(var):
            print(f"   ✅ {var}")
        else:
            print(f"   ❌ {var} (missing)")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing)}")
        print("Set them with:")
        for var in missing:
            print(f"   export {var}='your_value'")
        return False
    
    return True

async def main():
    """Main test function."""
    if not check_environment():
        sys.exit(1)
    
    success = await test_bot_startup()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 