# Railway Deployment Troubleshooting Guide

If your Railway deployment is hanging during the Docker import step, follow this guide to identify and fix the issue.

## Quick Diagnosis

### 1. Check Railway Logs
- Go to your Railway project dashboard
- Click on the deployment
- Check the logs for any error messages
- Look for where the process hangs

### 2. Use Debug Scripts

We've created several debug scripts to help identify the exact issue:

#### Option A: Use the Debug Dockerfile
1. Rename `Dockerfile.debug` to `Dockerfile`
2. Deploy to Railway
3. Check the logs for detailed import information

#### Option B: Use the Test Script
1. Deploy with the current Dockerfile
2. The `railway_test.py` script will run and show exactly where imports fail

## Common Issues and Solutions

### Issue 1: Import Hanging on nextcord
**Symptoms:** Build hangs when importing nextcord
**Solution:** 
- Check if you have conflicting Discord libraries
- Try updating to the latest nextcord version
- Ensure no discord.py is installed

### Issue 2: OpenAI Import Issues
**Symptoms:** Build hangs when importing openai
**Solution:**
- Check your OpenAI API key format
- Ensure the openai package version is compatible
- Try downgrading to a stable version

### Issue 3: Environment Variable Issues
**Symptoms:** Build succeeds but bot fails to start
**Solution:**
- Verify all required environment variables are set
- Check variable names and formats
- Use the validation script: `python3 check_variables.py`

### Issue 4: Memory Issues
**Symptoms:** Build times out or fails
**Solution:**
- Use the simplified web server (`web_main_simple.py`)
- Reduce dependency versions
- Use the debug Dockerfile to identify bottlenecks

## Debug Scripts

### `railway_test.py`
Basic import test that checks each dependency individually.

### `startup_debug.py`
Comprehensive startup test that checks:
- Basic Python imports
- Requirements imports
- Bot module imports
- Configuration loading
- Web server startup

### `check_variables.py`
Environment variable validation script.

## Alternative Deployment Methods

### Method 1: Use Railway's Python Template
1. Create a new Railway project
2. Choose "Python" template
3. Connect your GitHub repo
4. Set environment variables
5. Deploy

### Method 2: Use Railway's Docker Template
1. Create a new Railway project
2. Choose "Docker" template
3. Connect your GitHub repo
4. Set environment variables
5. Deploy

### Method 3: Use Heroku
1. Fork the repository
2. Connect to Heroku
3. Set environment variables
4. Deploy using the Procfile

## Environment Variable Checklist

Make sure you have all these variables set in Railway:

### Required:
- `badbot_discord_token` - Your Discord bot token
- `badbot_openai_key` - Your OpenAI API key
- `badbot_automod_servers` - Server configuration
- `badbot_automod_webhookurls` - Webhook URLs

### Optional:
- `openai_model` - OpenAI model (default: gpt-4o-mini)
- `openai_temperature` - Temperature (default: 0.0)

## Testing Locally

Before deploying to Railway, test locally:

```bash
# Test imports
python3 railway_test.py

# Test environment variables
python3 check_variables.py

# Test startup
python3 startup_debug.py
```

## Getting Help

If you're still having issues:

1. **Check Railway Status**: Visit [Railway Status](https://status.railway.app/)
2. **Check Logs**: Look at the detailed logs in Railway dashboard
3. **Try Debug Mode**: Use the debug Dockerfile to get more information
4. **Create Issue**: Open an issue in this repository with:
   - Railway logs
   - Environment variable status (without sensitive values)
   - Steps to reproduce

## Common Error Messages

### "Module not found"
- Check requirements.txt
- Verify package names
- Try reinstalling dependencies

### "Import timeout"
- Use debug scripts to identify slow imports
- Check for circular imports
- Simplify the import chain

### "Environment variable missing"
- Use `check_variables.py` to validate
- Check variable names (case-sensitive)
- Ensure all required variables are set

### "Permission denied"
- Check file permissions
- Verify Dockerfile syntax
- Ensure proper file ownership 