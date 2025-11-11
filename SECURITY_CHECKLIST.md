# 🔒 Security Checklist for Deployment

## ✅ Pre-Commit Security Checklist

Use this checklist **before every commit** to ensure you're not exposing sensitive data.

### 1. Credential Scanning

- [ ] No passwords in committed files
- [ ] No API keys in committed files
- [ ] No database connection strings with passwords
- [ ] No authentication tokens
- [ ] No private keys (.pem, .key files)
- [ ] No OAuth secrets or client secrets

**Quick Check:**
```bash
# Search for potential secrets in staged files
git diff --cached | grep -iE '(password|secret|api_key|token|credential)'
```

---

### 2. Environment Files

- [ ] `.env` is gitignored
- [ ] `.env.local` is gitignored
- [ ] `.env.production` is gitignored
- [ ] `.mcp.json` is gitignored
- [ ] Only `.env.example` or `.env.template` files are committed
- [ ] Template files use placeholder values (e.g., `YOUR_PASSWORD_HERE`)

**Verify:**
```bash
git check-ignore .env .mcp.json
# Should output: .env .mcp.json
```

---

### 3. Configuration Files

- [ ] `app.yaml` has no hardcoded credentials
- [ ] `docker-compose.yml` uses environment variables
- [ ] Config files use `${VARIABLE_NAME}` syntax
- [ ] Database connection strings use placeholders
- [ ] API endpoints don't include auth tokens in URLs
- [ ] Network binding is secure (see Network Security section)

**Check app.yaml:**
```bash
grep -iE "(password|api_key|secret).*:" .do/app.yaml
# Should only show variable declarations, not actual values
```

---

### 4. Documentation Files

- [ ] README has no real credentials
- [ ] Documentation uses example/placeholder credentials
- [ ] Setup guides reference environment variables
- [ ] No screenshots with visible secrets

**Files to Review:**
- `README.md`
- `DEPLOYMENT_*.md`
- `SETUP_*.md`
- Any `.txt` or `.md` files with "credential" or "config" in name

---

### 5. Source Code

- [ ] No hardcoded database passwords
- [ ] No hardcoded API keys
- [ ] Using `os.getenv()` or `process.env` for secrets
- [ ] No commented-out credentials
- [ ] No debug prints with sensitive data

**Scan Python files:**
```bash
grep -r "password.*=.*['\"]" --include="*.py" src/
# Should return nothing or only test/example values
```

---

### 6. Git History

- [ ] No credentials in previous commits
- [ ] `.env` was never committed (even if later removed)
- [ ] No secrets in commit messages
- [ ] No force-pushes that might expose history

**Check history:**
```bash
git log --all --full-history --source -- .env
# Should return nothing if .env was never committed
```

---

## 🛡️ Deployment Security Checklist

### 1. DigitalOcean App Platform

- [ ] Secrets stored in App Platform Console (not in app.yaml)
- [ ] Environment variables marked as "Secret" type
- [ ] Database passwords encrypted
- [ ] API keys encrypted
- [ ] App spec uses variable references only

**How to Add Secrets:**
1. Go to: App → Settings → Environment Variables
2. Click "Add Variable"
3. Check "Encrypt" for sensitive values
4. Save and redeploy

---

### 2. Supabase Database

- [ ] Database password is strong (16+ characters)
- [ ] SSL/TLS enabled for connections
- [ ] Connection pooling configured
- [ ] Row-Level Security (RLS) policies enabled
- [ ] Only necessary ports exposed

**Supabase Security Settings:**
```
✓ Connection Mode: Transaction (via pgBouncer)
✓ SSL Mode: require
✓ Connection Limit: 1 per worker
✓ Public Access: Only via API with authentication
```

---

### 3. Binance API

- [ ] Using testnet for development
- [ ] API keys have IP restrictions (if possible)
- [ ] API keys have permission restrictions
- [ ] Separate keys for testnet and production
- [ ] Keys stored as encrypted environment variables

**Binance API Security:**
```
✓ Environment: Testnet (for testing)
✓ Permissions: Only necessary permissions enabled
✓ IP Whitelist: Configured (if available)
✓ Never commit: Real production keys
```

---

### 4. Network Security

- [ ] HTTPS enforced for all endpoints
- [ ] CORS configured properly
- [ ] Rate limiting enabled
- [ ] No debug endpoints in production
- [ ] Health check doesn't expose sensitive info

**HTTPS Verification:**
```bash
curl -I https://your-app.ondigitalocean.app
# Should show: Strict-Transport-Security header
```

---

## 🚨 Security Issues You're Currently Missing

### 1. **No Dependency Scanning** ⚠️

**What's Missing:**
- No automated scanning for vulnerable packages
- No alerts for security updates

**Fix:**
```bash
# Add to your project
pip install safety

# Run security scan
safety check --json

# Add to CI/CD
echo "safety check" >> .github/workflows/security.yml
```

**Add to requirements.txt:**
```txt
safety>=2.3.0  # Security scanner
```

---

### 2. **No Secrets Detection in CI/CD** ⚠️

**What's Missing:**
- No pre-commit hooks to prevent credential commits
- No GitHub secret scanning alerts

**Fix:**

Create `.github/workflows/security-scan.yml`:
```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: TruffleHog Secrets Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: main
```

**Also add pre-commit hook:**
```bash
# Install detect-secrets
pip install detect-secrets

# Create baseline
detect-secrets scan > .secrets.baseline

# Add to .git/hooks/pre-commit
detect-secrets-hook --baseline .secrets.baseline
```

---

### 3. **No Database Access Controls** ⚠️

**What's Missing:**
- No Row-Level Security (RLS) policies in Supabase
- All authenticated users can read/write all data
- No audit logging

**Fix in Supabase:**
```sql
-- Enable RLS on all tables
ALTER TABLE trading.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading.trades ENABLE ROW LEVEL SECURITY;

-- Create policies (example: users can only see their own data)
CREATE POLICY "Users can view own accounts"
  ON trading.accounts FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own accounts"
  ON trading.accounts FOR INSERT
  WITH CHECK (auth.uid() = user_id);
```

---

### 4. **No Rate Limiting** ⚠️

**What's Missing:**
- API endpoints have no rate limiting
- Vulnerable to DDoS attacks
- No protection against API abuse

**Fix:**
```python
# Add to src/api/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to routes
@app.get("/api/portfolio")
@limiter.limit("30/minute")
async def get_portfolio():
    ...
```

**Add to requirements.txt:**
```txt
slowapi>=0.1.9  # Rate limiting
```

---

### 5. **No Input Validation** ⚠️

**What's Missing:**
- Limited validation of user inputs
- Potential for injection attacks
- No sanitization of outputs

**Fix:**
```python
# Use Pydantic models for all API inputs
from pydantic import BaseModel, Field, validator

class TradeRequest(BaseModel):
    symbol: str = Field(..., regex="^[A-Z]+$", max_length=10)
    quantity: float = Field(..., gt=0, le=1000000)
    price: float = Field(..., gt=0)

    @validator('symbol')
    def validate_symbol(cls, v):
        # Whitelist allowed symbols
        allowed = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        if v not in allowed:
            raise ValueError(f"Symbol must be one of {allowed}")
        return v
```

---

### 6. **No Security Headers** ⚠️

**What's Missing:**
- No Content-Security-Policy
- No X-Frame-Options
- No X-Content-Type-Options
- Vulnerable to XSS and clickjacking

**Fix:**
```python
# Add to src/api/main.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Force HTTPS in production
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

### 7. **No Logging/Monitoring for Security Events** ⚠️

**What's Missing:**
- No logging of failed authentication attempts
- No alerts for suspicious activity
- No audit trail

**Fix:**
```python
# Add security event logging
import logging
from datetime import datetime

security_logger = logging.getLogger("security")
security_logger.setLevel(logging.WARNING)

# Add handler for security events
handler = logging.FileHandler("security.log")
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
security_logger.addHandler(handler)

# Log security events
def log_security_event(event_type: str, details: dict):
    security_logger.warning(
        f"SECURITY_EVENT: {event_type}",
        extra={"event": event_type, "details": details, "timestamp": datetime.utcnow()}
    )

# Example usage
@app.post("/api/trades")
async def create_trade(trade: TradeRequest):
    try:
        # Process trade
        ...
    except Exception as e:
        log_security_event("TRADE_FAILED", {
            "symbol": trade.symbol,
            "error": str(e),
            "ip": request.client.host
        })
```

---

### 8. **No Backup and Recovery Plan** ⚠️

**What's Missing:**
- No automated database backups
- No disaster recovery plan
- No tested restore procedure

**Fix:**

**Enable Supabase Backups:**
1. Go to: Supabase Dashboard → Database → Backups
2. Enable daily backups (free tier has 7 days retention)
3. Test restore procedure monthly

**Create backup script:**
```bash
#!/bin/bash
# backup-database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/db_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

# Backup database (without password in script)
pg_dump "$DATABASE_URL" > "$BACKUP_FILE"

# Compress
gzip "$BACKUP_FILE"

# Upload to secure storage (e.g., S3)
# aws s3 cp "$BACKUP_FILE.gz" s3://your-backup-bucket/

echo "Backup completed: $BACKUP_FILE.gz"
```

---

### 9. **No WAF (Web Application Firewall)** ⚠️

**What's Missing:**
- No protection against common web attacks
- No bot detection
- No geographic filtering

**Fix:**

**Option 1: Use Cloudflare (Free)**
1. Add your domain to Cloudflare
2. Enable "I'm Under Attack" mode when needed
3. Configure firewall rules
4. Enable bot protection

**Option 2: DigitalOcean App Platform + Cloud Firewall**
```bash
# Create firewall rules via doctl
doctl compute firewall create \
  --name "app-firewall" \
  --inbound-rules "protocol:tcp,ports:443,sources:addresses:0.0.0.0/0" \
  --outbound-rules "protocol:tcp,ports:all,destinations:addresses:0.0.0.0/0"
```

---

### 10. **No Security Testing** ⚠️

**What's Missing:**
- No automated security tests
- No penetration testing
- No vulnerability assessments

**Fix:**

**Add to `.github/workflows/security-test.yml`:**
```yaml
name: Security Tests

on: [push, pull_request]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit (Python security scanner)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json

      - name: Run Safety (dependency scanner)
        run: |
          pip install safety
          safety check --json

      - name: OWASP Dependency Check
        uses: dependency-check/Dependency-Check_Action@main
        with:
          project: 'quant-analysis'
          path: '.'
          format: 'HTML'
```

**Add security tests:**
```python
# tests/test_security.py
import pytest
from fastapi.testclient import TestClient

def test_no_sensitive_data_in_errors(client: TestClient):
    """Ensure error messages don't leak sensitive info"""
    response = client.post("/api/invalid-endpoint")
    assert "password" not in response.text.lower()
    assert "secret" not in response.text.lower()
    assert "token" not in response.text.lower()

def test_sql_injection_protection(client: TestClient):
    """Test SQL injection protection"""
    response = client.get("/api/trades?symbol='; DROP TABLE trades;--")
    assert response.status_code != 500
    # Should return 400 or 422 (validation error)

def test_xss_protection(client: TestClient):
    """Test XSS protection"""
    response = client.post("/api/trades", json={
        "symbol": "<script>alert('xss')</script>",
        "quantity": 1,
        "price": 100
    })
    assert response.status_code == 422  # Validation error
```

---

## 📋 Quick Security Scan Commands

Run these before every commit:

```bash
# 1. Check for hardcoded secrets
grep -r "password\s*=\s*['\"]" --include="*.py" src/

# 2. Check for API keys
grep -r "api_key\s*=\s*['\"]" --include="*.py" src/

# 3. Verify .env is gitignored
git check-ignore .env

# 4. Check staged files for secrets
git diff --cached | grep -iE "(password|secret|api_key|token)"

# 5. Scan dependencies for vulnerabilities
pip install safety && safety check

# 6. Check for exposed files
git status --short | grep -E "\.env$|\.mcp\.json$|credentials"
```

---

## ✅ Current Security Status

**✓ Implemented:**
- Environment variables properly gitignored
- Credentials removed from app.yaml
- Template files with placeholders
- SQL injection protection (parameterized queries)
- SSL/TLS for database connections

**✗ Missing (High Priority):**
1. Dependency scanning (safety, bandit)
2. Pre-commit hooks for secret detection
3. Row-Level Security in Supabase
4. Rate limiting on API endpoints
5. Security headers middleware
6. Automated backups
7. Security event logging
8. Security testing in CI/CD

---

## 🎯 Recommended Implementation Order

### Week 1 (Critical):
1. Add dependency scanning (`safety check`)
2. Configure pre-commit hooks for secret detection
3. Enable Supabase RLS policies
4. Add rate limiting to API

### Week 2 (High Priority):
5. Implement security headers
6. Set up automated backups
7. Add security event logging
8. Configure WAF (Cloudflare)

### Week 3 (Medium Priority):
9. Add security tests to CI/CD
10. Implement input validation for all endpoints
11. Set up monitoring and alerts
12. Document incident response plan

---

## 📞 Security Incident Response

If you discover a security issue:

1. **Don't panic** - Most issues can be fixed
2. **Assess impact** - What data was exposed?
3. **Rotate credentials** - Change all affected passwords/keys immediately
4. **Check logs** - Look for unauthorized access
5. **Patch vulnerability** - Fix the root cause
6. **Document** - Record what happened and how you fixed it

**Emergency Credential Rotation:**
```bash
# 1. Generate new Supabase password (in Supabase dashboard)
# 2. Update DigitalOcean environment variables
# 3. Trigger redeploy
# 4. Revoke old credentials
```

---

## ✨ Final Pre-Commit Check

Before running `git commit`, answer these questions:

- [ ] Have I reviewed all staged files?
- [ ] Are there any passwords or API keys?
- [ ] Have I run `git diff --cached` to verify changes?
- [ ] Is `.env` still gitignored?
- [ ] Have I tested locally with the new changes?
- [ ] Have I run the security scan commands above?

**If YES to all, you're ready to commit! 🚀**

---

## 🔗 Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Supabase Security Guide](https://supabase.com/docs/guides/database/database-security)
- [DigitalOcean Security](https://docs.digitalocean.com/products/app-platform/how-to/manage-environment-variables/)
- [Git Secrets Prevention](https://github.com/awslabs/git-secrets)
