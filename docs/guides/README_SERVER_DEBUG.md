# 🔧 Server Connection Debug Guide

## ✅ **ISSUE RESOLVED: localhost:8000 Connection Fixed**

The localhost:8000 connection issue has been diagnosed and resolved. Here's what was wrong and how to fix it:

## 🐛 **Root Causes Identified**

1. **Missing Dependencies**: FastAPI and Uvicorn were not installed
2. **Virtual Environment**: Python packages were not in the correct environment
3. **Port Configuration**: Original server was configured for port 8001, not 8000

## 🚀 **Quick Fix - Start the Server**

### **Option 1: Automated Startup (Recommended)**
```bash
./start_trading_server.sh
```

### **Option 2: Manual Steps**
```bash
# 1. Activate virtual environment
source venv_trading/bin/activate

# 2. Install dependencies (if needed)
pip install fastapi uvicorn[standard] websockets

# 3. Start server
python start_server.py
```

### **Option 3: Test Server (Basic connectivity test)**
```bash
python simple_test_server.py
```

## 🌐 **Access Points**

After starting the server, access these URLs:

- **Main Dashboard**: http://localhost:8000
- **Backtesting Dashboard**: http://localhost:8000/backtesting.html
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🔍 **Diagnostic Tools**

### **Run Full Diagnostics**
```bash
python debug_server.py
```

This will check:
- ✅ Python environment status
- ✅ Dependency installation
- ✅ Project file structure
- ✅ Port availability
- ✅ Import functionality

### **Test Basic Connectivity**
```bash
# Check if server is running
curl http://localhost:8000/health

# Check API endpoint
curl http://localhost:8000/api/test
```

## 📋 **Common Issues & Solutions**

### **1. "No module named 'fastapi'"**
**Solution**: Install dependencies in virtual environment
```bash
source venv_trading/bin/activate
pip install fastapi uvicorn
```

### **2. "Port 8000 already in use"**
**Solution**: Kill existing process or use different port
```bash
# Kill process on port 8000
sudo lsof -ti:8000 | xargs kill -9

# Or start on different port
python start_server.py --port 8001
```

### **3. "Virtual environment not active"**
**Solution**: Activate virtual environment first
```bash
source venv_trading/bin/activate
# Check activation with:
which python
```

### **4. "Permission denied"**
**Solution**: Make scripts executable
```bash
chmod +x start_trading_server.sh
chmod +x debug_server.py
```

## 🛠️ **Server Configuration**

The server is configured with:
- **Host**: 0.0.0.0 (accessible from any IP)
- **Port**: 8000 (changed from 8001)
- **Auto-reload**: Enabled for development
- **CORS**: Enabled for frontend access

## 📊 **Verification Steps**

1. **Basic Server Test**:
   ```bash
   python simple_test_server.py
   # Visit: http://localhost:8000
   ```

2. **Full FastAPI Server**:
   ```bash
   source venv_trading/bin/activate
   python start_server.py
   # Visit: http://localhost:8000
   ```

3. **API Documentation**:
   ```bash
   # After server is running
   # Visit: http://localhost:8000/docs
   ```

## 🔧 **Environment Setup**

### **Virtual Environment**
```bash
# Create (if doesn't exist)
python3 -m venv venv_trading

# Activate
source venv_trading/bin/activate

# Verify activation
which python  # Should show venv_trading/bin/python
```

### **Dependencies Installation**
```bash
# Core FastAPI
pip install fastapi uvicorn[standard]

# Trading system
pip install websockets pandas numpy yfinance backtrader matplotlib

# Database (optional)
pip install psycopg2-binary asyncpg

# Visualization
pip install plotly streamlit
```

## 📈 **Testing the Trading System**

After the server is running:

1. **Dashboard Test**: Visit http://localhost:8000
2. **Backtesting Test**: Visit http://localhost:8000/backtesting.html
3. **API Test**: Visit http://localhost:8000/docs
4. **Health Check**: curl http://localhost:8000/health

## 🔍 **Advanced Troubleshooting**

### **Check Server Logs**
```bash
# Start server with verbose logging
source venv_trading/bin/activate
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

### **Network Diagnostics**
```bash
# Check if port is open
netstat -tulpn | grep :8000

# Check firewall (Ubuntu/Debian)
sudo ufw status

# Test from another machine
curl http://YOUR_IP:8000/health
```

### **Browser Developer Tools**
1. Open browser console (F12)
2. Check for JavaScript errors
3. Verify network requests to API endpoints
4. Check WebSocket connections

## 🎯 **Next Steps**

1. ✅ Server connectivity established
2. ✅ Basic FastAPI endpoint working
3. ✅ Virtual environment configured
4. 🔄 Test backtesting dashboard functionality
5. 🔄 Verify Interactive Brokers integration
6. 🔄 Test risk management features

## 📞 **Still Having Issues?**

Run the comprehensive diagnostic:
```bash
python debug_server.py
```

This will provide detailed information about:
- Environment status
- Missing dependencies
- File structure issues
- Port conflicts
- Import problems

The debug tool will give specific solutions for each issue found.

---

## ✅ **SUCCESS INDICATORS**

When everything is working correctly, you should see:

1. **Server Output**:
   ```
   🚀 Starting Quantitative Trading Dashboard
   📡 API Server: http://localhost:8000
   📊 Dashboard: http://localhost:8000
   📚 API Docs: http://localhost:8000/docs
   ```

2. **Browser Access**:
   - Main page loads without errors
   - API documentation accessible at /docs
   - Health check returns {"status": "healthy"}

3. **No Error Messages**:
   - No "ModuleNotFoundError"
   - No "Connection refused"
   - No "Port already in use"

**🎉 Once you see these indicators, the server is fully operational!**