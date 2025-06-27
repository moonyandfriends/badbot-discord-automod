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

### 3. Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd badbot-discord-automod
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create credential files:
   - Create `token.txt` with your Discord bot token
   - Create `openai.txt` with your OpenAI API key

4. Configure the bot:
   - Edit `config.json` with your server and webhook configurations
   - Update server IDs, names, and log channel IDs
   - Add your webhook URLs

### 4. Configuration

Edit `config.json` to configure your servers and webhooks:

```json
{
  "servers": [
    {
      "guild_id": 123456789012345678,
      "guild_name": "My Server",
      "log_channel_id": 987654321098765432
    }
  ],
  "webhooks": [
    {
      "url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL",
      "name": "Notification Channel"
    }
  ]
}
```

### 5. Running the Bot

```bash
python main.py
```

## How It Works

1. **AutoMod Event Detection**: The bot listens for AutoMod events across all configured servers
2. **Content Analysis**: When a message is blocked by AutoMod, it's sent to GPT-4 for scam detection
3. **Scam Confirmation**: If GPT-4 confirms it's a scam, the user is banned from all monitored servers
4. **Notifications**: Webhook notifications are sent with details about the banned user and scam message
5. **Logging**: All actions are logged to the respective server's log channel

## Configuration Details

### Server Configuration
- `guild_id`: The Discord server ID
- `guild_name`: Human-readable server name (for logging)
- `log_channel_id`: Channel ID where bot logs will be posted

### Webhook Configuration
- `url`: Discord webhook URL for notifications
- `name`: Human-readable name for the webhook (for logging)

## File Structure

```
badbot-discord-automod/
├── main.py              # Main bot code
├── config.json          # Server and webhook configuration
├── requirements.txt     # Python dependencies
├── token.txt           # Discord bot token (create this)
├── openai.txt          # OpenAI API key (create this)
└── README.md           # This file
```

## Security Considerations

- Keep your bot token and API keys secure
- Never commit credential files to version control
- Use environment variables in production
- Regularly rotate API keys
- Monitor bot logs for suspicious activity

## Troubleshooting

### Common Issues

1. **Bot can't access servers**: Ensure the bot is invited to all configured servers with proper permissions
2. **Ban failures**: Check that the bot has "Ban Members" permission in all servers
3. **Webhook errors**: Verify webhook URLs are valid and accessible
4. **GPT-4 errors**: Check your OpenAI API key and account status

### Logging

The bot provides detailed logging at INFO level. Check the console output for:
- Server connection status
- AutoMod event processing
- GPT-4 analysis results
- Ban operation results
- Webhook notification status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.