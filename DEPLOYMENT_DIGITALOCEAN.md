# DigitalOcean Deployment Guide
## 24/7 Cloud Deployment for Quantitative Trading Dashboard

---

## 📋 Prerequisites

1. **DigitalOcean Account** with credit card attached (free $200 credit for new users!)
2. **Binance Testnet API Keys** (free, no signup): https://testnet.binance.vision/
3. **GitHub Repository** (push your code to GitHub)
4. **doctl CLI** (optional, for command-line deployment)

---

## 🚀 Deployment Methods

### **Method 1: Web Console (Easiest - Recommended)**

#### Step 1: Prepare Your GitHub Repository

```bash
# Push your code to GitHub
git add .
git commit -m "Prepare for DigitalOcean deployment"
git push origin master
```

#### Step 2: Update App Spec

Edit [.do/app.yaml](.do/app.yaml) and update:

```yaml
services:
  - name: api
    github:
      repo: YOUR_GITHUB_USERNAME/YOUR_REPO_NAME  # <-- Update this!
      branch: master
```

Also update Redis worker if using:

```yaml
workers:
  - name: trading-redis
    github:
      repo: YOUR_GITHUB_USERNAME/YOUR_REPO_NAME  # <-- Update this!
```

#### Step 3: Get Binance API Keys

1. Visit: https://testnet.binance.vision/
2. Click **"Generate HMAC_SHA256 Key"**
3. Save your API Key and Secret (you'll need these)

#### Step 4: Deploy to DigitalOcean

1. **Log in** to [DigitalOcean Console](https://cloud.digitalocean.com/)
2. Click **"Create" → "App Platform"**
3. Choose **"GitHub"** as source
4. Select your repository
5. **Upload** `.do/app.yaml` spec file
6. Review the configuration:
   - ✅ API service (basic-xxs, $12/month)
   - ✅ PostgreSQL database (dev, $15/month)
   - ✅ Redis worker (basic-xxs, $12/month)
7. **Add Environment Secrets**:
   - `BINANCE_TESTNET_API_KEY` = Your API key
   - `BINANCE_TESTNET_API_SECRET` = Your API secret
8. Click **"Create Resources"**

#### Step 5: Wait for Deployment

- ⏱️ First deployment: 5-10 minutes
- 📊 Watch the build logs in real-time
- ✅ Success when status = "Active"

#### Step 6: Access Your App

```
https://trading-dashboard-xxxxx.ondigitalocean.app
```

Test the API:
```bash
curl https://your-app-url.ondigitalocean.app/health
```

---

### **Method 2: Command Line (doctl)**

#### Step 1: Install doctl

```bash
# macOS
brew install doctl

# Linux
cd ~
wget https://github.com/digitalocean/doctl/releases/download/v1.98.0/doctl-1.98.0-linux-amd64.tar.gz
tar xf doctl-1.98.0-linux-amd64.tar.gz
sudo mv doctl /usr/local/bin

# Windows (PowerShell)
choco install doctl
```

#### Step 2: Authenticate

```bash
doctl auth init
# Enter your DigitalOcean API token
```

#### Step 3: Update App Spec

Edit `.do/app.yaml`:
- Update GitHub repo URL
- Add your Binance API keys (or set as secrets later)

#### Step 4: Create App

```bash
# Create the app
doctl apps create --spec .do/app.yaml

# Get app ID from output
export APP_ID=<your-app-id>

# Add secrets
doctl apps update $APP_ID --env-secret BINANCE_TESTNET_API_KEY=your_key_here
doctl apps update $APP_ID --env-secret BINANCE_TESTNET_API_SECRET=your_secret_here
```

#### Step 5: Monitor Deployment

```bash
# Watch deployment progress
doctl apps list

# View logs
doctl apps logs $APP_ID --type build
doctl apps logs $APP_ID --type deploy

# Get app info
doctl apps get $APP_ID
```

---

## 💰 Cost Breakdown

### **Starter Configuration (Testnet Trading)**

| Component | Tier | Monthly Cost |
|-----------|------|--------------|
| API Service | basic-xxs (512MB RAM, 1 vCPU) | $12 |
| PostgreSQL DB | Dev (1GB RAM, 10GB storage) | $15 |
| Redis Worker | basic-xxs (512MB RAM) | $12 |
| **Total** | | **$39/month** |

### **Production Configuration (Real Trading)**

| Component | Tier | Monthly Cost |
|-----------|------|--------------|
| API Service | basic-s (2GB RAM, 2 vCPU) | $48 |
| PostgreSQL DB | Production (4GB RAM, 50GB) | $60 |
| Redis Worker | basic-xs (1GB RAM) | $24 |
| **Total** | | **$132/month** |

### **Budget Configuration (Minimal)**

| Component | Tier | Monthly Cost |
|-----------|------|--------------|
| API Service | basic-xxs (512MB RAM) | $12 |
| PostgreSQL DB | Dev (1GB RAM) | $15 |
| Skip Redis | Use in-memory cache | $0 |
| **Total** | | **$27/month** |

---

## 🔧 Configuration Options

### **Enable Automated Trading**

In `.do/app.yaml`, change:

```yaml
- key: BINANCE_ENABLE_BOTS
  value: "true"  # Enable bots
```

### **Switch to Live Trading (Real Money!)**

⚠️ **WARNING: Use real money only after thorough testing!**

```yaml
- key: CURRENT_PIPELINE
  value: "binance_live"  # Switch to live trading

- key: BINANCE_LIVE_API_KEY
  value: "YOUR_REAL_API_KEY"
  type: SECRET

- key: BINANCE_LIVE_API_SECRET
  value: "YOUR_REAL_SECRET"
  type: SECRET
```

### **Scale Your API**

```yaml
services:
  - name: api
    instance_size_slug: basic-s  # Upgrade to 2GB RAM
    instance_count: 2  # Run 2 instances for high availability
```

### **Add Custom Domain**

1. Go to **App Settings → Domains**
2. Add your domain: `trading.yourdomain.com`
3. Update DNS:
   ```
   CNAME trading -> trading-dashboard-xxxxx.ondigitalocean.app
   ```
4. SSL certificate auto-generated!

---

## 🔐 Security Best Practices

### **1. Use Secrets for API Keys**

Never commit API keys to GitHub!

```bash
# Add secrets via doctl
doctl apps update $APP_ID \
  --env-secret BINANCE_TESTNET_API_KEY=your_key \
  --env-secret BINANCE_TESTNET_API_SECRET=your_secret \
  --env-secret POSTGRES_PASSWORD=random_password_here
```

### **2. Enable Database Encryption**

In `.do/app.yaml`:

```yaml
databases:
  - name: trading-postgres
    production: true  # Production DBs have encryption at rest
```

### **3. Restrict Database Access**

```bash
# Only allow app to access DB (done automatically by DO)
# DB is in private network, not exposed to internet
```

### **4. Use Environment-Specific Configs**

```yaml
# Dev environment
- key: BINANCE_TEST_MODE
  value: "true"

# Production environment (only after testing!)
- key: BINANCE_TEST_MODE
  value: "false"
```

---

## 📊 Monitoring & Logs

### **View Logs (Web Console)**

1. Go to **App → Runtime Logs**
2. Select component: `api`, `trading-redis`, or `trading-postgres`
3. Filter by log level: INFO, ERROR, DEBUG

### **View Logs (CLI)**

```bash
# Real-time logs
doctl apps logs $APP_ID --type run --follow

# Build logs
doctl apps logs $APP_ID --type build

# Deploy logs
doctl apps logs $APP_ID --type deploy
```

### **Health Checks**

Your app has automatic health monitoring:

```bash
# Check app status
curl https://your-app.ondigitalocean.app/health

# Response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### **Alerts**

Set up alerts in DigitalOcean:

1. Go to **Monitoring → Alerting**
2. Create alert for:
   - CPU usage > 80%
   - Memory usage > 90%
   - App crashes
   - Health check failures

---

## 🚨 Troubleshooting

### **Build Fails**

```bash
# Check build logs
doctl apps logs $APP_ID --type build

# Common issues:
# 1. Missing dependencies in requirements.txt
# 2. Dockerfile syntax errors
# 3. GitHub repo not accessible
```

**Fix:**
```bash
# Verify Dockerfile builds locally
docker build -t test-api .

# Test locally
docker run -p 8000:8000 test-api
```

### **Database Connection Fails**

**Symptoms:**
- API crashes on startup
- Error: "connection refused"

**Fix:**

1. Check database status:
```bash
doctl databases list
```

2. Verify connection string:
```bash
doctl apps spec get $APP_ID
# Check DATABASE_URL is correct
```

3. Check firewall rules:
```bash
doctl databases firewall list <db-id>
# Should show "app:$APP_ID" as trusted source
```

### **App Crashes Repeatedly**

```bash
# Check runtime logs
doctl apps logs $APP_ID --type run --tail 100

# Check resource limits
doctl apps get $APP_ID
# Look at instance_size_slug - may need upgrade
```

**Common causes:**
- Out of memory (upgrade to basic-xs or basic-s)
- Missing environment variables
- Database connection issues

### **Slow Performance**

1. **Upgrade instance size**:
```yaml
instance_size_slug: basic-s  # 2GB RAM instead of 512MB
```

2. **Add Redis caching**:
```yaml
workers:
  - name: trading-redis  # Uncomment Redis worker
```

3. **Enable horizontal scaling**:
```yaml
instance_count: 2  # Run multiple API instances
```

---

## 🔄 Updates & Maintenance

### **Deploy Updates**

```bash
# Push to GitHub
git add .
git commit -m "Update trading strategy"
git push origin master

# Auto-deploy happens automatically!
# Or manually trigger:
doctl apps create-deployment $APP_ID
```

### **Rollback**

```bash
# List deployments
doctl apps list-deployments $APP_ID

# Rollback to previous deployment
doctl apps create-deployment $APP_ID --deployment-id <previous-deployment-id>
```

### **Backup Database**

```bash
# List databases
doctl databases list

# Create backup
doctl databases backups create <db-id>

# List backups
doctl databases backups list <db-id>

# Restore from backup
doctl databases backups restore <db-id> <backup-id>
```

### **Update Environment Variables**

```bash
# Update single variable
doctl apps update $APP_ID --env BINANCE_ENABLE_BOTS=true

# Update spec file
doctl apps update $APP_ID --spec .do/app.yaml
```

---

## 🎯 Next Steps

### **After Successful Deployment**

1. ✅ **Test the API**:
   ```bash
   curl https://your-app.ondigitalocean.app/api/v1/market/symbols
   ```

2. ✅ **Access the Dashboard**:
   ```
   https://your-app.ondigitalocean.app/dashboard
   ```

3. ✅ **Monitor Performance**:
   - Check logs for errors
   - Watch resource usage (CPU, RAM)
   - Set up alerts

4. ✅ **Run Backtests**:
   ```bash
   curl -X POST https://your-app.ondigitalocean.app/api/v1/backtesting/run \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "BTCUSDT",
       "strategy": "MovingAverageCrossover",
       "start_date": "2023-01-01",
       "end_date": "2024-01-01"
     }'
   ```

5. ✅ **Enable Bots** (after testing):
   - Update `BINANCE_ENABLE_BOTS=true`
   - Monitor bot performance
   - Start with small capital

### **Upgrade to Production**

When ready for real trading:

1. **Test thoroughly on testnet** (at least 1 month)
2. **Get Binance production API keys**:
   - https://www.binance.com/en/my/settings/api-management
   - Enable **Spot Trading** only (no withdrawals!)
3. **Update app spec**:
   ```yaml
   - key: CURRENT_PIPELINE
     value: "binance_live"
   ```
4. **Add live API keys as secrets**
5. **Upgrade database to production tier**
6. **Start with minimal capital** ($100-$500)
7. **Monitor 24/7 for first week**

---

## 📞 Support

- **DigitalOcean Docs**: https://docs.digitalocean.com/products/app-platform/
- **Community Forum**: https://www.digitalocean.com/community/
- **Support Ticket**: https://cloud.digitalocean.com/support/tickets

---

## 🎉 Summary

You now have:

✅ **24/7 cloud deployment** - Always online, automatic restarts
✅ **Managed database** - PostgreSQL with automatic backups
✅ **Scalable infrastructure** - Easily upgrade as you grow
✅ **HTTPS + SSL** - Secure connections out of the box
✅ **Auto-deploys** - Push to GitHub, automatically deploys
✅ **Monitoring** - Built-in health checks and alerts
✅ **Low cost** - Starting at $27/month

**Total deployment time: 10-15 minutes! 🚀**
