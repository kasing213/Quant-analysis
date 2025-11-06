#!/usr/bin/env python3
"""
Simple FastAPI test without database initialization
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import time

# Application startup time for uptime calculation
startup_time = time.time()

app = FastAPI(
    title="Quantitative Trading Portfolio API - Test",
    description="Simple test version without database",
    version="2.0.0-test",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enhanced CORS configuration for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"]
)

@app.get("/", tags=["System"])
async def root():
    """API root endpoint with system information"""
    uptime_seconds = time.time() - startup_time
    return {
        "service": "Quantitative Trading Portfolio API - Test",
        "version": "2.0.0-test",
        "status": "operational",
        "uptime_seconds": round(uptime_seconds, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "FastAPI is working - database disabled for testing"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "portfolio-api-test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - startup_time, 2),
        "database": "disabled for testing"
    }

@app.get("/test", tags=["Test"])
async def test_endpoint():
    """Test endpoint to verify API functionality"""
    return {
        "message": "FastAPI test successful!",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "working"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)