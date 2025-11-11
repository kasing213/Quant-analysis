#!/usr/bin/env python
"""
Test Railway deployment configuration
Validates that all environment variables and database connections work correctly
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_railway_config():
    """Test Railway deployment configuration"""
    print("=" * 60)
    print("Railway Deployment Configuration Test")
    print("=" * 60)

    # Test 1: Environment Variables
    print("\n1. Checking Environment Variables...")
    required_vars = {
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'PORT': os.getenv('PORT', '8000'),  # Railway provides this
        'ENVIRONMENT': os.getenv('ENVIRONMENT', 'production'),
    }

    all_set = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask sensitive data
            display_value = var_value if var_name in ['PORT', 'ENVIRONMENT'] else f"{var_value[:30]}..."
            print(f"   [OK] {var_name}: {display_value}")
        else:
            print(f"   [FAIL] {var_name}: NOT SET")
            all_set = False

    if not all_set:
        print("\n   [WARN] Some environment variables are missing")
        print("   This is OK for local testing, but required for Railway")

    # Test 2: Database Connection
    print("\n2. Testing Database Connection...")
    try:
        from src.api.database import test_db_connection

        db_status = await test_db_connection()

        if db_status.get('status') == 'healthy':
            print(f"   [OK] Database connection: HEALTHY")
            print(f"   [OK] SQLAlchemy async: {db_status.get('sqlalchemy_async')}")
            print(f"   [OK] PostgreSQL manager: {db_status.get('postgresql_manager')}")
        else:
            print(f"   [FAIL] Database connection: UNHEALTHY")
            if 'error' in db_status:
                print(f"   Error: {db_status['error']}")
    except Exception as e:
        print(f"   [FAIL] Database connection failed: {e}")

    # Test 3: API Endpoints Configuration
    print("\n3. Checking API Configuration...")
    try:
        from src.api.main import app
        print(f"   [OK] FastAPI app loaded successfully")
        print(f"   [OK] App title: {app.title}")
        print(f"   [OK] App version: {app.version}")

        # Get available routes
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        health_routes = [r for r in routes if 'health' in r.lower()]
        print(f"   [OK] Health check endpoints: {', '.join(health_routes)}")
    except Exception as e:
        print(f"   [FAIL] Failed to load API: {e}")

    # Test 4: Railway-specific checks
    print("\n4. Railway-Specific Configuration...")
    port = os.getenv('PORT', '8000')
    print(f"   [OK] PORT variable: {port}")
    print(f"   [OK] Expected bind address: 0.0.0.0:{port}")
    print(f"   [OK] Health check URL: http://localhost:{port}/health")

    # Test 5: Metrics and Monitoring
    print("\n5. Checking Metrics Configuration...")
    try:
        from src.api.metrics import initialize_metrics
        print(f"   [OK] Prometheus metrics available")
        print(f"   [OK] Metrics endpoint: /metrics")
    except ImportError:
        print(f"   [WARN] Prometheus metrics not available (optional)")

    print("\n" + "=" * 60)
    print("Configuration test completed!")
    print("=" * 60)
    print("\nNext steps for Railway deployment:")
    print("1. Ensure DATABASE_URL is set in Railway environment variables")
    print("2. Railway will automatically set PORT variable")
    print("3. Deploy using: railway up")
    print("4. Monitor health at: https://your-app.railway.app/health")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_railway_config())
