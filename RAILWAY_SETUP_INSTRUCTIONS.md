# Railway Environment Variables Setup - Windows Instructions

## The Problem
Railway deployment shows `[Errno 111] Connection refused` because environment variables are not set in Railway.

## Two Methods to Fix This

---

## Method 1: Railway Dashboard (EASIEST - 5 minutes) ⭐

### Step 1: Open Railway Dashboard
Go to: https://railway.com/project/1e9b72e3-d91e-4a04-aca3-19c606b3f967/settings

### Step 2: Click "Shared Variables" in Left Sidebar
Or go directly to variables page

### Step 3: Click "+ New Variable"

### Step 4: Add These Variables One by One

Copy these **exactly** (variable name on first line, value on second line):

```
DATABASE_URL
postgresql://postgres.wsqwoeqetggqkktkgoxo:Kasingchan223699.@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres

POSTGRES_HOST
db.wsqwoeqetggqkktkgoxo.supabase.co

POSTGRES_PORT
5432

POSTGRES_DB
postgres

POSTGRES_USER
postgres.wsqwoeqetggqkktkgoxo

POSTGRES_PASSWORD
Kasingchan223699.

SUPABASE_PROJECT_REF
wsqwoeqetggqkktkgoxo

SUPABASE_API_KEY
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzcXdvZXFldGdncWtrdGtnb3hvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI0Mjc0NTQsImV4cCI6MjA3ODAwMzQ1NH0.OTqXvP_39_ITnw6y6yPyOSL2Jd_G6QcIRo5YX8U4I7g

BINANCE_API_KEY
PmgwBzsmqGLgMfonaqubsYeST93bIc3tSKssSAkuhAQMnDXz4cwQPuahqUWJuqLW

BINANCE_API_SECRET
e8iXttPORabKs5v3ghj3PX5vSDVy04sUYSGRL54UazWL9xWYqSiShLrs5WU6r1iv

BINANCE_TESTNET
true

BINANCE_TEST_MODE
true

CURRENT_PIPELINE
binance_paper

REDIS_ENABLED
false

ENVIRONMENT
production

DEBUG
false

LOG_LEVEL
INFO

MPLCONFIGDIR
/tmp/matplotlib
```

### Step 5: Click "Deploy" or Wait for Auto-Deploy

Railway will automatically redeploy with the new variables.

---

## Method 2: Railway CLI from PowerShell (FAST - 2 minutes)

### Prerequisites
- You're already logged in: ✅ `kasingchan213@gmail.com`
- Project linked: ✅ `intelligent-clarity` → `production` → `Quant-analysis`

### Option A: Run the Batch Script

Open PowerShell in `d:\Tiktok-analyzing` and run:

```powershell
.\railway_setup_windows.bat
```

### Option B: Run Commands Manually

Open PowerShell and run these commands:

```powershell
cd "d:\Tiktok-analyzing"

# Set all variables at once (faster!)
railway variables `
  --set "DATABASE_URL=postgresql://postgres.wsqwoeqetggqkktkgoxo:Kasingchan223699.@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres" `
  --set "POSTGRES_HOST=db.wsqwoeqetggqkktkgoxo.supabase.co" `
  --set "POSTGRES_PORT=5432" `
  --set "POSTGRES_DB=postgres" `
  --set "POSTGRES_USER=postgres.wsqwoeqetggqkktkgoxo" `
  --set "POSTGRES_PASSWORD=Kasingchan223699." `
  --set "SUPABASE_PROJECT_REF=wsqwoeqetggqkktkgoxo" `
  --set "SUPABASE_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndzcXdvZXFldGdncWtrdGtnb3hvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI0Mjc0NTQsImV4cCI6MjA3ODAwMzQ1NH0.OTqXvP_39_ITnw6y6yPyOSL2Jd_G6QcIRo5YX8U4I7g" `
  --set "BINANCE_API_KEY=PmgwBzsmqGLgMfonaqubsYeST93bIc3tSKssSAkuhAQMnDXz4cwQPuahqUWJuqLW" `
  --set "BINANCE_API_SECRET=e8iXttPORabKs5v3ghj3PX5vSDVy04sUYSGRL54UazWL9xWYqSiShLrs5WU6r1iv" `
  --set "BINANCE_TESTNET=true" `
  --set "BINANCE_TEST_MODE=true" `
  --set "CURRENT_PIPELINE=binance_paper" `
  --set "REDIS_ENABLED=false" `
  --set "ENVIRONMENT=production" `
  --set "DEBUG=false" `
  --set "LOG_LEVEL=INFO" `
  --set "MPLCONFIGDIR=/tmp/matplotlib"

# Verify variables were set
railway variables

# Variables are set! Railway will auto-deploy
```

---

## Fixing the "Access Denied" Error for `railway up`

If you get "Access is denied. (os error 5)" when running `railway up`, try:

### Solution 1: Run PowerShell as Administrator
1. Right-click PowerShell
2. Select "Run as Administrator"
3. Navigate to project: `cd "d:\Tiktok-analyzing"`
4. Try `railway up` again

### Solution 2: Use Git Bash Instead
```bash
cd /d/Tiktok-analyzing
railway up
```

### Solution 3: Push to GitHub and Let Railway Auto-Deploy
If `railway up` keeps failing:

```powershell
# Commit your changes (including the Dockerfile fix)
git add Dockerfile
git commit -m "Fix Supabase connection and matplotlib permissions"
git push origin master

# Railway will automatically detect the push and deploy
```

---

## Verification

### Check Variables Are Set
```powershell
railway variables
```

You should see all your DATABASE_URL, POSTGRES_*, BINANCE_*, etc. variables listed.

### Check Deployment Logs
```powershell
railway logs
```

Look for:
- ✅ `PostgreSQL connection pools initialized`
- ✅ `Database initialization completed successfully`
- ❌ No more `[Errno 111] Connection refused`

### Test the Deployment
Once deployed, test your health endpoint:

```powershell
# Get your Railway URL
railway domain

# Test it
curl https://your-app.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## Quick Troubleshooting

**Q: Variables not showing up?**
- Make sure you're in the `production` environment
- Click the environment dropdown in Railway dashboard

**Q: Still getting connection refused?**
- Wait 2-3 minutes for deployment to complete
- Check logs: `railway logs`
- Verify DATABASE_URL is exactly correct (no typos)

**Q: railway up still shows "Access denied"?**
- Use Railway Dashboard method instead
- Or push to GitHub and let Railway auto-deploy
- Or run PowerShell as Administrator

**Q: Want to see current deployment?**
```powershell
railway status
railway logs -f  # Follow logs in real-time
```

---

## Important Notes

✅ Your local connection test passed - credentials are correct
✅ Using Session Pooler (port 5432) - compatible with asyncpg  
✅ Matplotlib cache fix already in Dockerfile
⚠️ Never commit .env file to git (already in .gitignore)
💡 Railway auto-deploys when you set variables in the dashboard
💡 Railway auto-deploys when you push to GitHub (if connected)

---

## Summary

**Fastest Method**: Use Railway Dashboard (Method 1) ⭐

**CLI Method**: Run the PowerShell commands (Method 2) if you prefer command line

**After Setting Variables**: Railway will auto-deploy. Check logs with `railway logs`

That's it! Your Supabase connection will work once these variables are set.
