# 🤖 Bad Bot Auto Mod

A Discord bot that monitors AutoMod events, uses ChatGPT to detect scams, bans users across multiple servers, and sends webhook notifications.

## ✨ Features

- **Multi-Server Monitoring**: Monitors AutoMod events across multiple Discord servers
- **AI Scam Detection**: Uses ChatGPT to analyze flagged messages for scam content
- **Cross-Server Banning**: Automatically bans detected scammers from all configured servers
- **Webhook Notifications**: Sends detailed notifications to Discord webhooks
- **Duplicate Prevention**: Prevents processing the same user multiple times
- **Rate Limiting**: Built-in delays to avoid Discord API rate limits
- **Robust Error Handling**: Comprehensive error handling and validation
- **Permission Checking**: Verifies bot permissions on startup

## 🔧 How It Works

1. Bot monitors AutoMod events in configured servers
2. When a message is blocked by AutoMod, it's analyzed by ChatGPT
3. If ChatGPT determines it's a scam, the user is banned from all servers
4. Notifications are sent to all configured webhooks
5. Duplicate processing is prevented for the same user

## 🤖 Bot Info

Your Discord bot only needs the **Ban Members** permission to function properly.

### Quick Add Bot
[Add Bad Bot to your server](https://discord.com/oauth2/authorize?client_id=1385655724960645200&permissions=4&scope=bot)

## ⚙️ Environment Variables

Set these in your Railway dashboard:

### Required Variables
- `badbot_discord_token` - Your Discord bot token
- `badbot_openai_key` - Your OpenAI API key
- `badbot_automod_servers` - Server configuration in format: `guildID|guildName,guildID2|guildName2`
- `badbot_automod_webhookurls` - Webhook URLs separated by commas

### Optional Variables
- `openai_model` - OpenAI model to use (default: "gpt-4o-mini")

### Example Configuration

**Servers Format:**
```
badbot_automod_servers=988945059783278602|Stride,798583171548840026|Osmosis,862470645316845568|Ion
```

**Webhooks Format:**
```
badbot_automod_webhookurls=https://discord.com/api/webhooks/123/abc,https://discord.com/api/webhooks/456/def
```

**Optional Model Configuration:**
```
openai_model=gpt-4o-mini
```

**IMPORTANT:** 
- Use exact format: `guildID|guildName` (pipe separator)
- No spaces after commas in webhook URLs
- Server names can contain spaces but avoid special characters
- Webhook URLs are automatically validated on startup

## 🚀 Railway Deployment

1. Fork this repository
2. Connect your Railway account to GitHub
3. Create a new Railway project from your fork
4. Set the environment variables in Railway dashboard
5. Deploy!

**Required Permission:**
- `Ban Members` - To ban users from servers 