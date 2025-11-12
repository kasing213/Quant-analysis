# Supabase Connection Fix - Summary

## Problem Identified
Your Railway deployment was showing `[Errno 111] Connection refused` when trying to connect to Supabase PostgreSQL database.

## Root Cause
Railway doesn't automatically import environment variables from your local `.env` file. The `DATABASE_URL` and related PostgreSQL variables were missing in Railway's environment.

## What We Fixed

### 1. ✅ Verified Local Connection Works
- Created and ran `test_supabase_connection.py`
- **Result**: Connection works perfectly from your local machine
- Database: PostgreSQL 17.6 on Supabase
- Connection: Using Session Pooler (recommended for asyncpg)

### 2. ✅ Created Railway Setup Guide
- **File**: `RAILWAY_SUPABASE_SETUP.md`
- Contains step-by-step instructions for setting Railway environment variables
- Two methods: Dashboard (easy) and CLI (automated)

### 3. ✅ Created Automated Setup Script
- **File**: `railway_env_setup.sh`
- One-command setup for all Railway environment variables
- Includes database, Supabase, Binance, and application settings

### 4. ✅ Fixed Matplotlib Warning
- **Issue**: `mkdir -p failed for path /home/appuser/.config/matplotlib: [Errno 13] Permission denied`
- **Fix**: Updated [Dockerfile](Dockerfile) to:
  - Set `MPLCONFIGDIR=/tmp/matplotlib` environment variable
  - Create `/tmp/matplotlib` directory with proper permissions
  - This prevents matplotlib from trying to write to restricted directories

## Required Environment Variables for Railway

You need to set these in Railway (via Dashboard or CLI):

```bash
# Database Connection (PRIMARY - most important!)
DATABASE_URL=postgresql://postgres.wsqwoeqetggqkktkgoxo:Kasingchan223699.@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres

# Database Individual Settings (backup)
POSTGRES_HOST=db.wsqwoeqetggqkktkgoxo.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres.wsqwoeqetggqkktkgoxo
POSTGRES_PASSWORD=Kasingchan223699.

# Supabase API
SUPABASE_PROJECT_REF=wsqwoeqetggqkktkgoxo
SUPABASE_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzcXdvZXFldGdncWtrdGtnb3hvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI0Mjc0NTQsImV4cCI6MjA3ODAwMzQ1NH0.OTqXvP_39_ITnw6y6yPyOSL2Jd_G6QcIRo5YX8U4I7g

# Binance Testnet
BINANCE_API_KEY=PmgwBzsmqGLgMfonaqubsYeST93bIc3tSKssSAkuhAQMnDXz4cwQPuahqUWJuqLW
BINANCE_API_SECRET=e8iXttPORabKs5v3ghj3PX5vSDVy04sUYSGRL54UazWL9xWYqSiShLrs5WU6r1iv
BINANCE_TESTNET=true
BINANCE_TEST_MODE=true

# Application Settings
CURRENT_PIPELINE=binance_paper
REDIS_ENABLED=false
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
MPLCONFIGDIR=/tmp/matplotlib
```

## How to Deploy the Fix

### Option 1: Using Railway Dashboard (Recommended)

1. Go to https://railway.app/dashboard
2. Select your project
3. Click on your service
4. Go to **Variables** tab
5. Add all the environment variables listed above
6. Click **Deploy**

### Option 2: Using Railway CLI

```bash
# Make sure you're linked to your project
railway link

# Run the automated setup script
./railway_env_setup.sh

# Or set variables manually using the commands in RAILWAY_SUPABASE_SETUP.md

# Deploy
railway up
```

## Verification Steps

After deploying:

1. **Check Railway logs**:
   ```bash
   railway logs
   ```

2. **Look for success messages**:
   ```
   ✅ PostgreSQL connection pools initialized
   ✅ Database initialization completed successfully
   ✅ Portfolio API startup completed successfully
   ```

3. **Test health endpoint**:
   ```bash
   curl https://your-app.railway.app/health
   ```

   Should return:
   ```json
   {
     "status": "healthy",
     "environment": "production",
     "database": "connected"
   }
   ```

## What Should Disappear

After fixing:
- ❌ `[Errno 111] Connection refused` errors
- ❌ Matplotlib permission warnings
- ❌ "Database initialization failed" messages
- ❌ "Continuing without database - API will run in limited mode"

## What Should Appear

After fixing:
- ✅ `PostgreSQL connection pools initialized`
- ✅ `Database initialization completed successfully`
- ✅ Successful health check responses
- ✅ Clean startup logs without errors

## Files Created

1. **test_supabase_connection.py** - Test database connection locally
2. **RAILWAY_SUPABASE_SETUP.md** - Detailed setup instructions
3. **railway_env_setup.sh** - Automated Railway variable setup script
4. **SUPABASE_FIX_SUMMARY.md** - This summary document

## Modified Files

1. **[Dockerfile](Dockerfile)** - Added matplotlib cache directory fix

## Next Actions

1. **Set Railway environment variables** (use one of the methods above)
2. **Redeploy your application**
3. **Monitor logs** for successful database connection
4. **Test the application** to ensure everything works

## Important Notes

- ✅ Local connection test passed - your credentials are correct
- ✅ Using Session Pooler (port 5432) - compatible with asyncpg
- ✅ Region: AWS ap-southeast-2 (Sydney) - matches Supabase
- ⚠️ Never commit `.env` file to git (already in .gitignore)
- ⚠️ Consider rotating credentials if they were exposed
- 💡 Railway requires explicit environment variable configuration
- 💡 Matplotlib now uses `/tmp/matplotlib` for cache (writable)

## Troubleshooting

If you still have issues after setting variables:

1. Verify variables are set in Railway dashboard
2. Check Supabase status: https://status.supabase.com
3. Ensure Railway service has internet access
4. Review logs for detailed error messages
5. Test connection locally: `python test_supabase_connection.py`

## Support

If you need help:
- Railway Docs: https://docs.railway.app
- Supabase Docs: https://supabase.com/docs
- Check Railway logs: `railway logs -f`
- Check Supabase dashboard for connection issues
