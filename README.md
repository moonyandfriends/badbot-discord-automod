# BadBot Discord AutoMod

A Discord bot that monitors AutoMod events across multiple servers and uses AI to detect and respond to potential scams.

## Features

- **Multi-Server Monitoring**: Monitors AutoMod events across multiple Discord servers
- **AI-Powered Detection**: Uses OpenAI GPT-4 to analyze flagged messages for scam detection
- **Cross-Server Bans**: Automatically bans detected scammers from all monitored servers
- **Webhook Notifications**: Sends detailed notifications via Discord webhooks
- **Server-Specific Webhooks**: Support for server-specific notification channels

## Configuration

The bot uses environment variables for all configuration. No config files needed!

### Required Environment Variables

- `badbot_discord_token`: Your Discord bot token
- `badbot_openai_key`: Your OpenAI API key  
- `badbot_automod_servers`: Comma-separated list of servers to monitor
- `badbot_automod_webhookurls`: Comma-separated list of webhook URLs for notifications

### Optional Environment Variables

- `openai_model`: OpenAI model to use (default: "gpt-4o-mini")
- `openai_temperature`: Temperature for OpenAI API calls (default: 0.0)

### Configuration Format

**Server Configuration:**
```
badbot_automod_servers=123456789012345678|My Server Name,987654321098765432|Another Server
```

**Webhook Configuration:**
```
badbot_automod_webhookurls=https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnop,https://discord.com/api/webhooks/987654321098765432/qrstuvwxyz123456
```

**Server-Specific Webhooks (Optional):**
```
badbot_automod_webhookurls=https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnop|My Server Name,https://discord.com/api/webhooks/987654321098765432/qrstuvwxyz123456|Another Server,https://discord.com/api/webhooks/111222333444555666/fallback789|General
```

## Deployment

### Railway Deployment

1. Fork this repository
2. Connect your Railway account to GitHub
3. Create a new Railway project from your fork
4. Set the environment variables in Railway dashboard
5. Deploy!

The bot will automatically:
- Monitor all channels in configured servers for AutoMod events
- Use AI to analyze flagged messages
- Ban scammers from all monitored servers
- Send notifications via webhooks

### Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables
4. Run: `python main.py`

## How It Works

1. **AutoMod Detection**: Bot listens for AutoMod action executions across all monitored servers
2. **AI Analysis**: Flagged messages are sent to OpenAI GPT-4 for scam detection
3. **Cross-Server Banning**: If a scam is detected, the user is banned from all monitored servers
4. **Webhook Notifications**: Detailed notifications are sent to configured webhooks

## Security

- All configuration is done via environment variables
- No sensitive data is stored in code
- Webhook URLs are validated before use
- Bot only responds to AutoMod events from configured servers

## Support

For issues or questions, please check the Railway logs or create an issue in this repository.