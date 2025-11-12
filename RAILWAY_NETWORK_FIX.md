# Railway Network Connection Issue - Fix Guide

## Current Error
```
[Errno 101] Network is unreachable
```

This means Railway's container cannot reach Supabase's database servers.

## Solution 1: Switch to Direct Connection (Try This First)

### Step 1: Edit DATABASE_URL in Railway Dashboard

1. Go to: https://railway.com/project/1e9b72e3-d91e-4a04-aca3-19c606b3f967/settings/variables
2. Find `DATABASE_URL` variable
3. Click to edit
4. Change value to:
   ```
   postgresql://postgres.wsqwoeqetggqkktkgoxo:Kasingchan223699.@db.wsqwoeqetggqkktkgoxo.supabase.co:5432/postgres
   ```
   (Changed from `aws-1-ap-southeast-2.pooler.supabase.com` to `db.wsqwoeqetggqkktkgoxo.supabase.co`)

5. Save and wait for auto-deploy (2-3 minutes)

### Step 2: Check Logs
```powershell
railway logs
```

Look for:
- ✅ `PostgreSQL connection pools initialized`
- ❌ No more `Network is unreachable`

## Solution 2: Use IPv4-Only Pooler

If direct connection doesn't work, try the IPv4 pooler:

1. Edit `DATABASE_URL` again
2. Use this value:
   ```
   postgresql://postgres.wsqwoeqetggqkktkgoxo:Kasingchan223699.@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres
   ```
   (Note: `aws-0` instead of `aws-1`)

## Solution 3: Check Supabase Firewall Settings

### Step 1: Allow Railway's IP Range

1. Go to Supabase dashboard: https://supabase.com/dashboard/project/wsqwoeqetggqkktkgoxo/settings/database
2. Scroll to **Connection Pooling** section
3. Check if there are any IP restrictions
4. If restricted, you need to allow Railway's IPs

### To Get Railway's IP Addresses:

Create a temporary debug endpoint in your app or use Railway's network info.

Railway typically uses IP ranges from:
- `35.x.x.x` (US regions)
- `3.x.x.x` (AWS regions)

But the easiest solution is to **allow all IPs** in Supabase (if security permits):
- Set connection pooling to allow `0.0.0.0/0` (all IPs)

## Solution 4: Use Supabase Connection String from Dashboard

### Get Fresh Connection String

1. Go to: https://supabase.com/dashboard/project/wsqwoeqetggqkktkgoxo/settings/database
2. Under **Connection string**, select **URI** format
3. Choose **Session mode** (not Transaction mode)
4. Copy the connection string
5. Replace `[YOUR-PASSWORD]` with `Kasingchan223699.`
6. Update `DATABASE_URL` in Railway with this exact string

## Troubleshooting

### Check if Supabase is Accessible from Railway

You can add a health check endpoint to test connectivity:

```python
@app.get("/debug/network")
async def debug_network():
    import socket
    results = {}
    
    # Test direct connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("db.wsqwoeqetggqkktkgoxo.supabase.co", 5432))
        sock.close()
        results["direct"] = "reachable" if result == 0 else f"unreachable (code: {result})"
    except Exception as e:
        results["direct"] = f"error: {e}"
    
    # Test pooler connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("aws-1-ap-southeast-2.pooler.supabase.com", 5432))
        sock.close()
        results["pooler"] = "reachable" if result == 0 else f"unreachable (code: {result})"
    except Exception as e:
        results["pooler"] = f"error: {e}"
    
    return results
```

Then access: `https://your-app.railway.app/debug/network`

## Common Causes

1. **Railway's IPv6 limitations**: Some Railway regions only support IPv4
2. **Supabase pooler regional restrictions**: Pooler might not be accessible from all regions
3. **Firewall rules**: Supabase might have IP restrictions enabled
4. **Network policy**: Railway project might have network policies blocking external databases

## Recommended Fix Order

1. ✅ **Try direct connection** (most likely to work)
2. If that fails, try IPv4 pooler
3. If that fails, check Supabase firewall settings
4. If all fails, contact Railway support about outbound database connections

## After Fixing

Once connected, you should see:
```
✓ DATABASE_URL is configured
✓ PostgreSQL connection pools initialized (async: 5-25)
✓ Database initialization completed successfully
```

No more network errors!
