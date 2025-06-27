#!/usr/bin/env python3
"""
Startup debug script for Railway.
This will help identify exactly where the import process is hanging.
"""

import sys
import os
import time

def log(message):
    """Log with timestamp and flush immediately."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)

def main():
    """Main debug function."""
    log("🚀 Railway Startup Debug - Starting")
    log(f"Python: {sys.version}")
    log(f"Platform: {sys.platform}")
    log(f"Working dir: {os.getcwd()}")
    log(f"Files in dir: {os.listdir('.')}")
    
    # Test 1: Basic imports
    log("Step 1: Testing basic imports...")
    try:
        import json
        log("✅ json imported")
    except Exception as e:
        log(f"❌ json failed: {e}")
        return 1
    
    # Test 2: Requirements imports
    log("Step 2: Testing requirements imports...")
    
    modules = ["nextcord", "openai", "aiohttp", "fastapi", "uvicorn"]
    
    for module in modules:
        try:
            log(f"Testing {module}...")
            __import__(module)
            log(f"✅ {module} imported")
        except Exception as e:
            log(f"❌ {module} failed: {e}")
            return 1
    
    # Test 3: Our bot import
    log("Step 3: Testing bot import...")
    try:
        log("Importing main.py...")
        import main
        log("✅ main.py imported")
    except Exception as e:
        log(f"❌ main.py failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 4: Bot instance creation
    log("Step 4: Testing bot instance creation...")
    try:
        bot = main.BadBotAutoMod()
        log("✅ BadBotAutoMod instance created")
    except Exception as e:
        log(f"❌ Bot instance creation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 5: Config loading
    log("Step 5: Testing config loading...")
    try:
        bot.load_config()
        log("✅ Config loaded")
    except Exception as e:
        log(f"❌ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 6: Credentials loading
    log("Step 6: Testing credentials loading...")
    try:
        token = bot.load_credentials()
        log("✅ Credentials loaded")
    except Exception as e:
        log(f"❌ Credentials loading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 7: Web server import
    log("Step 7: Testing web server import...")
    try:
        import web_main_simple
        log("✅ web_main_simple imported")
    except Exception as e:
        log(f"❌ web_main_simple failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    log("🎉 All tests passed! Starting web server...")
    
    # Start the web server
    import uvicorn
    from web_main_simple import app
    
    port = int(os.environ.get("PORT", 8000))
    log(f"Starting uvicorn on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    log(f"Startup debug completed with exit code: {exit_code}")
    sys.exit(exit_code) 