# BadBot Discord AutoMod

A Discord bot that monitors AutoMod events across multiple servers and uses GPT-4 to detect scam messages. When a scam is detected, the user is automatically banned from all configured servers and notifications are sent to webhooks.

## Features

- **Multi-Server Monitoring**: Monitors AutoMod events across multiple Discord servers
- **AI-Powered Scam Detection**: Uses GPT-4 to analyze flagged messages for scam content
- **Cross-Server Banning**: Automatically bans scammers from all monitored servers
- **Webhook Notifications**: Sends detailed notifications to configured Discord webhooks
- **Rate Limiting**: Implements 2-second delays between bans and webhook posts
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Duplicate Prevention**: Prevents processing the same user multiple times
- **Environment-Based Configuration**: Uses environment variables for secure configuration

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- Discord Bot Token with appropriate permissions
- OpenAI API Key
- Discord servers with AutoMod enabled
- Discord webhook URLs for notifications

### 2. Bot Permissions

Your Discord bot needs the following permissions:
- `Ban Members` - To ban users from servers
- `View Channels` - To access log channels
- `Send Messages` - To send notifications
- `Embed Links` - To send rich embed notifications
- `Read Message History` - To access message content

### 3. Local Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd badbot-discord-automod
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export badbot_discord_token="your_discord_bot_token"
export badbot_openai_key="your_openai_api_key"
export badbot_automod_servers="guildID1|guildName1|logChannelID1,guildID2|guildName2|logChannelID2"
export badbot_automod_webhookurls="webhook1|servername1,webhook2|servername2,webhook3"
export openai_model="gpt-4o-mini"
export openai_temperature="0.0"
```

4. Run the bot:
```bash
python main.py
```

### 4. Railway Deployment

This bot is configured for easy deployment on Railway:

1. **Fork or clone this repository** to your GitHub account

2. **Connect to Railway**:
   - Go to [Railway.app](https://railway.app)
   - Create a new project
   - Choose "Deploy from GitHub repo"
   - Select this repository

3. **Configure Environment Variables** in Railway:
   - `badbot_discord_token`: Your Discord bot token
   - `badbot_openai_key`: Your OpenAI API key
   - `badbot_automod_servers`: Server configuration (see format below)
   - `badbot_automod_webhookurls`: Comma-separated webhook URLs with optional server names (see format below)
   - `openai_model`: OpenAI model to use (default: gpt-4o-mini)
   - `openai_temperature`: Temperature for OpenAI responses (default: 0.0)

4. **Deploy**: Railway will automatically build and deploy your bot

#### Alternative Deployment Methods

**If Railway builds hang or fail:**

1. **Use Docker Deployment**:
   - Railway supports Dockerfile deployment
   - The included Dockerfile provides a more reliable build process
   - Set Railway to use Docker instead of Nixpacks

2. **Use Heroku**:
   - Deploy using the included Procfile
   - Set environment variables in Heroku dashboard
   - Use `heroku container:push web` for Docker deployment

3. **Use DigitalOcean App Platform**:
   - Supports Python apps directly
   - Set environment variables in the dashboard
   - Uses the included Dockerfile

#### Troubleshooting Railway Build Issues

**If builds hang on Nixpacks:**
1. **Try Docker deployment** instead of Nixpacks
2. **Check Railway logs** for specific error messages
3. **Verify environment variables** are set correctly
4. **Use the test script** locally: `python test_startup.py`

**Common issues:**
- **Build timeout**: Use Dockerfile instead of Nixpacks
- **Dependency conflicts**: Check requirements.txt versions
- **Environment variables**: Ensure all required variables are set

## Configuration

### Environment Variables

#### Required Variables
- `badbot_discord_token`: Your Discord bot token
- `badbot_openai_key`: Your OpenAI API key
- `badbot_automod_servers`: Server configuration in format: `guildID|guildName|logChannelID,guildID2|guildName2|logChannelID2`

#### Optional Variables
- `badbot_automod_webhookurls`: Comma-separated webhook URLs for notifications
- `openai_model`: OpenAI model to use (default: gpt-4o-mini)
- `openai_temperature`: Temperature for OpenAI responses (default: 0.0)

### Server Configuration Format

The `badbot_automod_servers` environment variable uses this format:
```
guildID1|guildName1|logChannelID1,guildID2|guildName2|logChannelID2
```

**Important:** Uses pipe separators (`|`) to avoid conflicts with server names containing colons, emojis, or special characters.

Examples:
```
# Basic server configuration
988945059783278602|Server 1|1336461137767563304,798583171548840026|Server 2|1336503006623170580

# Server names with special characters
988945059783278602|🚨 Alert Server|1336461137767563304,798583171548840026|Main: Gaming Server|1336503006623170580
```

### Webhook Configuration

The `badbot_automod_webhookurls` environment variable supports two formats:

#### Server-Specific Webhooks (Recommended)
Format: `webhookURL|servername,webhookURL2|servername2`

**Important:** Uses the pipe character (`|`) as separator to avoid conflicts with URLs and server names containing colons.

Examples:
```
# Correct - server name after pipe separator
https://discord.com/api/webhooks/123456789/abcdef|Server 1
https://discord.com/api/webhooks/987654321/xyz123|Server 2

# Works with server names containing colons, emojis, etc.
https://discord.com/api/webhooks/123456789/abcdef|🚨 Alert Server
https://discord.com/api/webhooks/987654321/xyz123|Main: Gaming Server
```

**Benefits:**
- Notifications are sent to the specific server's webhook when a scam is detected
- If no server-specific webhook is found, falls back to general webhooks
- Better organization and targeted notifications
- No conflicts with URLs or server names containing colons, emojis, or special characters

#### General Webhooks (Legacy)
Format: `webhook1,webhook2,webhook3`

Examples:
```
https://discord.com/api/webhooks/123456789/abcdef,https://discord.com/api/webhooks/987654321/xyz123
```

**Note:** 
- Server names in webhooks must match the server names in `badbot_automod_servers` (case-insensitive)
- Uses pipe (`|`) as separator to avoid conflicts with colons in URLs or server names
- Supports server names with emojis, colons, and other special characters

## How It Works

1. **AutoMod Event Detection**: The bot listens for AutoMod events across all configured servers
2. **Content Analysis**: When a message is blocked by AutoMod, it's sent to GPT-4 for scam detection
3. **Scam Confirmation**: If GPT-4 confirms it's a scam, the user is banned from all monitored servers
4. **Notifications**: Webhook notifications are sent with details about the banned user and scam message
5. **Logging**: All actions are logged to the respective server's log channel

## File Structure

```
badbot-discord-automod/
├── main.py              # Main bot code
├── requirements.txt     # Python dependencies
├── railway.json         # Railway deployment configuration
├── Procfile            # Railway process file
├── runtime.txt         # Python version specification
└── README.md           # This file
```

## Security Considerations

- Keep your bot token and API keys secure
- Use environment variables for all sensitive configuration
- Never commit credentials to version control
- Regularly rotate API keys
- Monitor bot logs for suspicious activity

## Troubleshooting

### Common Issues

1. **Bot can't access servers**: Ensure the bot is invited to all configured servers with proper permissions
2. **Ban failures**: Check that the bot has "Ban Members" permission in all servers
3. **Webhook errors**: Verify webhook URLs are valid and accessible
4. **GPT-4 errors**: Check your OpenAI API key and account status
5. **Environment variable errors**: Ensure all required environment variables are set correctly

### Logging

The bot provides detailed logging at INFO level. Check the console output for:
- Server connection status
- AutoMod event processing
- GPT-4 analysis results
- Ban operation results
- Webhook notification status

### Railway-Specific Issues

1. **Build failures**: Check that all dependencies are listed in `requirements.txt`
2. **Runtime errors**: Verify all environment variables are set in Railway dashboard
3. **Bot not starting**: Check Railway logs for startup errors

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.