#!/usr/bin/env python3
"""
Debug script to identify import issues in the Discord bot.
This will help us figure out why Railway Docker builds are hanging.
"""

import sys
import os
import time

def test_import(module_name, description=""):
    """Test importing a specific module and report success/failure."""
    print(f"🔍 Testing import: {module_name} {description}")
    start_time = time.time()
    
    try:
        __import__(module_name)
        elapsed = time.time() - start_time
        print(f"✅ {module_name} imported successfully ({elapsed:.2f}s)")
        return True
    except ImportError as e:
        elapsed = time.time() - start_time
        print(f"❌ {module_name} import failed ({elapsed:.2f}s): {e}")
        return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"⚠️  {module_name} import error ({elapsed:.2f}s): {e}")
        return False

def test_system_info():
    """Display system information."""
    print("🖥️  System Information")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Executable: {sys.executable}")
    print(f"Path: {sys.path[:3]}...")  # First 3 entries
    print()

def test_requirements_imports():
    """Test all imports from requirements.txt."""
    print("📦 Testing Requirements.txt Imports")
    print("=" * 50)
    
    modules_to_test = [
        ("nextcord", "Discord API library"),
        ("openai", "OpenAI API client"),
        ("aiohttp", "Async HTTP client"),
        ("typing_extensions", "Type hints extensions"),
        ("fastapi", "Web framework"),
        ("uvicorn", "ASGI server"),
    ]
    
    results = []
    for module, description in modules_to_test:
        success = test_import(module, f"({description})")
        results.append((module, success))
        time.sleep(0.1)  # Small delay between imports
    
    print()
    print("📊 Import Results Summary:")
    print("=" * 30)
    failed = [module for module, success in results if not success]
    if failed:
        print(f"❌ Failed imports: {', '.join(failed)}")
        return False
    else:
        print("✅ All imports successful!")
        return True

def test_bot_imports():
    """Test importing our bot-specific modules."""
    print("\n🤖 Testing Bot-Specific Imports")
    print("=" * 50)
    
    # Test importing main bot components
    try:
        print("🔍 Testing main.py imports...")
        import main
        print("✅ main.py imported successfully")
        
        # Test creating bot instance
        print("🔍 Testing bot instance creation...")
        bot = main.BadBotAutoMod()
        print("✅ BadBotAutoMod instance created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Bot import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment():
    """Test environment variable loading."""
    print("\n🌍 Testing Environment Variables")
    print("=" * 50)
    
    required_vars = [
        "badbot_discord_token",
        "badbot_openai_key", 
        "badbot_automod_servers",
        "badbot_automod_webhookurls"
    ]
    
    optional_vars = [
        "openai_model",
        "openai_temperature"
    ]
    
    print("Required variables:")
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: Set ({len(str(value))} chars)")
        else:
            print(f"❌ {var}: Missing")
    
    print("\nOptional variables:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: Not set (will use default)")

def main():
    """Main debug function."""
    print("🚀 Discord Bot Import Debugger")
    print("=" * 60)
    print("This script will help identify why Railway Docker builds are hanging.")
    print()
    
    # Test system info
    test_system_info()
    
    # Test requirements imports
    requirements_ok = test_requirements_imports()
    
    if requirements_ok:
        # Test bot imports
        bot_ok = test_bot_imports()
        
        if bot_ok:
            # Test environment
            test_environment()
            
            print("\n🎉 All tests passed! The bot should work correctly.")
        else:
            print("\n❌ Bot-specific imports failed. Check the error above.")
    else:
        print("\n❌ Basic requirements imports failed. This is likely the cause of Railway hanging.")
    
    print("\n" + "=" * 60)
    print("Debug complete. Check the output above for issues.")

if __name__ == "__main__":
    main() 