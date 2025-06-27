# Railway Deployment Guide

## Quick Fix for Hanging Builds

If your Railway deployment is hanging on Nixpacks, follow these steps:

### Step 1: Force Docker Deployment

1. **Go to your Railway project dashboard**
2. **Navigate to Settings → General**
3. **Find "Build & Deploy" section**
4. **Change "Builder" from "Nixpacks" to "Dockerfile"**
5. **Save changes**

### Step 2: Redeploy

1. **Go to Deployments tab**
2. **Click "Deploy Now"**
3. **Select "Deploy from GitHub"**
4. **Choose your repository**

### Step 3: Set Environment Variables

In Railway dashboard → Variables, set:

```
badbot_discord_token=your_discord_bot_token
badbot_openai_key=your_openai_api_key
badbot_automod_servers=guildID1|guildName1|logChannelID1,guildID2|guildName2|logChannelID2
badbot_automod_webhookurls=webhook1|servername1,webhook2|servername2
openai_model=gpt-4o-mini
openai_temperature=0.0
```

## Alternative: Manual Docker Deployment

If Railway still hangs, deploy manually:

```bash
# Build Docker image
docker build -t badbot-discord-automod .

# Run locally to test
docker run -e badbot_discord_token=your_token -e badbot_openai_key=your_key -e badbot_automod_servers="guildID|guildName|logChannelID" badbot-discord-automod
```

## Troubleshooting

### Build Still Hangs
- **Check Railway logs** for specific errors
- **Try a different region** (us-west1, eu-west1)
- **Use Heroku** as alternative (supports Python apps directly)

### Environment Variables
- **Verify all required variables** are set
- **Check variable names** match exactly
- **Test locally** with `python test_startup.py`

### Bot Not Starting
- **Check Discord token** is valid
- **Verify bot permissions** in Discord
- **Check server IDs** are correct 