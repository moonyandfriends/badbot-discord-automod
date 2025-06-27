#!/usr/bin/env python3
"""
Environment variable checker for Railway deployment.
This script validates all required environment variables and their formats.
"""

import os
import sys

def check_required_variables():
    """Check if all required environment variables are set."""
    print("🔍 Checking Required Environment Variables")
    print("=" * 50)
    
    required_vars = {
        "badbot_discord_token": "Discord bot token (starts with MTA... or similar)",
        "badbot_openai_key": "OpenAI API key (starts with sk-...)",
        "badbot_automod_servers": "Server configuration (guildID|guildName|logChannelID format)"
    }
    
    missing_vars = []
    valid_vars = []
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value[:20]}..." if len(value) > 20 else f"✅ {var}: {value}")
            valid_vars.append(var)
        else:
            print(f"❌ {var}: MISSING - {description}")
            missing_vars.append(var)
    
    return missing_vars, valid_vars

def check_optional_variables():
    """Check optional environment variables."""
    print("\n🔍 Checking Optional Environment Variables")
    print("=" * 50)
    
    optional_vars = {
        "badbot_automod_webhookurls": "Webhook URLs (webhookURL|servername format)",
        "openai_model": "OpenAI model (default: gpt-4o-mini)",
        "openai_temperature": "Temperature (default: 0.0)"
    }
    
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: Not set (will use default) - {description}")

def validate_server_config(servers_env: str) -> bool:
    """Validate server configuration format."""
    if not servers_env:
        print("❌ badbot_automod_servers is empty")
        return False
    
    server_pairs = servers_env.split(',')
    valid_servers = 0
    
    for pair in server_pairs:
        if '|' in pair:
            parts = pair.strip().split('|')
            if len(parts) == 2:
                guild_id_str, guild_name = parts
                try:
                    guild_id = int(guild_id_str.strip())
                    if guild_name.strip():
                        valid_servers += 1
                        print(f"✅ Server: {guild_name.strip()} ({guild_id})")
                    else:
                        print(f"❌ Server name is empty: {pair}")
                except ValueError:
                    print(f"❌ Invalid server ID format: {pair}")
            else:
                print(f"❌ Invalid server format (expected guildID|guildName): {pair}")
        else:
            print(f"❌ Missing separator '|' in server config: {pair}")
    
    print(f"\n📊 Server Configuration Summary:")
    print(f"   Valid servers: {valid_servers}")
    print(f"   Total pairs: {len(server_pairs)}")
    
    return valid_servers > 0

def validate_webhook_format():
    """Validate the webhook configuration format."""
    print("\n🔍 Validating Webhook Configuration Format")
    print("=" * 50)
    
    webhooks_var = os.environ.get("badbot_automod_webhookurls")
    if not webhooks_var:
        print("⚠️  No webhooks configured (optional)")
        return True
    
    try:
        # Split by comma
        webhook_pairs = webhooks_var.split(',')
        print(f"Found {len(webhook_pairs)} webhook(s)")
        
        for i, pair in enumerate(webhook_pairs, 1):
            pair = pair.strip()
            if '|' in pair:
                # Server-specific webhook
                parts = pair.split('|', 1)
                webhook_url = parts[0].strip()
                server_name = parts[1].strip()
                
                if not webhook_url.startswith('http'):
                    print(f"❌ Webhook {i}: Invalid URL format - {webhook_url}")
                    return False
                
                print(f"✅ Webhook {i}: {server_name} - {webhook_url[:50]}...")
            else:
                # General webhook
                if not pair.startswith('http'):
                    print(f"❌ Webhook {i}: Invalid URL format - {pair}")
                    return False
                
                print(f"✅ Webhook {i}: General - {pair[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error parsing webhook configuration: {e}")
        return False

def validate_discord_token():
    """Validate Discord token format."""
    print("\n🔍 Validating Discord Token")
    print("=" * 50)
    
    token = os.environ.get("badbot_discord_token")
    if not token:
        print("❌ Discord token is missing")
        return False
    
    # Basic Discord token validation
    if len(token) < 50:
        print("❌ Discord token seems too short")
        return False
    
    if not any(prefix in token for prefix in ['MTA', 'MTI', 'OTk', 'ODc']):
        print("⚠️  Discord token format seems unusual (should start with MTA, MTI, OTk, or ODc)")
    
    print("✅ Discord token format looks valid")
    return True

def validate_openai_key():
    """Validate OpenAI API key format."""
    print("\n🔍 Validating OpenAI API Key")
    print("=" * 50)
    
    key = os.environ.get("badbot_openai_key")
    if not key:
        print("❌ OpenAI API key is missing")
        return False
    
    # Basic OpenAI key validation
    if not key.startswith('sk-'):
        print("❌ OpenAI API key should start with 'sk-'")
        return False
    
    if len(key) < 20:
        print("❌ OpenAI API key seems too short")
        return False
    
    print("✅ OpenAI API key format looks valid")
    return True

def main():
    """Main validation function."""
    print("🚀 Railway Environment Variable Validator")
    print("=" * 60)
    
    # Check required variables
    missing_vars, valid_vars = check_required_variables()
    
    # Check optional variables
    check_optional_variables()
    
    # Validate formats
    servers_env = os.environ.get("badbot_automod_servers")
    server_valid = validate_server_config(servers_env) if servers_env else False
    webhook_valid = validate_webhook_format()
    token_valid = validate_discord_token()
    openai_valid = validate_openai_key()
    
    # Summary
    print("\n📋 Summary")
    print("=" * 50)
    
    if missing_vars:
        print(f"❌ Missing required variables: {', '.join(missing_vars)}")
        print("\n🔧 Fix these in Railway dashboard:")
        for var in missing_vars:
            print(f"   {var} = your_value_here")
        return False
    
    if not all([server_valid, webhook_valid, token_valid, openai_valid]):
        print("❌ Some validations failed")
        return False
    
    print("✅ All environment variables are valid!")
    print("\n🚀 Your Railway deployment should work now.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 