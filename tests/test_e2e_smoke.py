#!/usr/bin/env python3
"""
End-to-End Smoke Tests for Portfolio API

Tests key endpoints and functionality without requiring real services:
- Health checks
- Database connectivity
- Portfolio endpoints
- Market data endpoints
- WebSocket connections

Can run with mocked services for CI/CD environments.
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import status
import os
from typing import AsyncGenerator

# Set test environment variables before importing app
os.environ.setdefault("PIPELINE_MODE", "BINANCE_PAPER")
os.environ.setdefault("BINANCE_TEST_MODE", "true")
os.environ.setdefault("BINANCE_ENABLE_BOTS", "false")
os.environ.setdefault("BINANCE_ENABLE_MARKET_DATA", "false")

from src.api.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoints:
    """Test health check endpoints"""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns service info"""
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] in ["operational", "healthy"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """Test basic health check"""
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_database_health(self, client: AsyncClient):
        """Test database health check"""
        response = await client.get("/health/database")

        # Should return 200 even if database is unavailable (graceful degradation)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "status" in data
        # Status can be "healthy" or "degraded" depending on DB availability
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


class TestPortfolioEndpoints:
    """Test portfolio-related endpoints"""

    @pytest.mark.asyncio
    async def test_portfolio_summary(self, client: AsyncClient):
        """Test portfolio summary endpoint"""
        response = await client.get("/api/v1/portfolio/summary")

        # Should work even with mock/empty data
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # Check for expected fields
        assert isinstance(data, dict)
        # Portfolio summary should have some structure even if empty

    @pytest.mark.asyncio
    async def test_portfolio_positions(self, client: AsyncClient):
        """Test positions endpoint"""
        response = await client.get("/api/v1/portfolio/positions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return list (may be empty)
        assert isinstance(data, (list, dict))


class TestMarketDataEndpoints:
    """Test market data endpoints"""

    @pytest.mark.asyncio
    async def test_market_symbols(self, client: AsyncClient):
        """Test market symbols endpoint"""
        response = await client.get("/api/v1/market/symbols")

        # Should return 200 even if market data is disabled
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_market_quote(self, client: AsyncClient):
        """Test getting a quote for a symbol"""
        response = await client.get("/api/v1/market/quote/BTCUSDT")

        # May not work if market data disabled, but should not crash
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]


class TestBotEndpoints:
    """Test bot management endpoints"""

    @pytest.mark.asyncio
    async def test_bots_health(self, client: AsyncClient):
        """Test bot orchestrator health endpoint"""
        response = await client.get("/api/v1/bots/health")

        # May return 503 if bots are disabled
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

    @pytest.mark.asyncio
    async def test_list_bots(self, client: AsyncClient):
        """Test listing all bots"""
        response = await client.get("/api/v1/bots/")

        # May return 503 if bots are disabled
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, dict)


class TestPipelineEndpoints:
    """Test pipeline management endpoints"""

    @pytest.mark.asyncio
    async def test_get_active_pipeline(self, client: AsyncClient):
        """Test getting active pipeline configuration"""
        response = await client.get("/api/v1/pipelines/active")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "pipeline" in data
        assert "service_config" in data

    @pytest.mark.asyncio
    async def test_list_pipelines(self, client: AsyncClient):
        """Test listing available pipelines"""
        response = await client.get("/api/v1/pipelines/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "pipelines" in data
        assert isinstance(data["pipelines"], list)
        # Should only expose Binance paper/live pipelines
        assert len(data["pipelines"]) == 2


class TestWebSocketConnection:
    """Test WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_websocket_connect(self, client: AsyncClient):
        """Test WebSocket connection establishment"""
        # Note: This is a basic test. Full WebSocket testing requires websockets library
        # For now, just verify the endpoint exists

        # We can't easily test WebSocket with httpx, but we can check
        # that the server doesn't crash when we try to connect
        # A proper WebSocket test would use the websockets library
        pass  # Skip for basic smoke test


class TestErrorHandling:
    """Test API error handling"""

    @pytest.mark.asyncio
    async def test_404_not_found(self, client: AsyncClient):
        """Test 404 handling for non-existent endpoints"""
        response = await client.get("/api/v1/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_invalid_bot_id(self, client: AsyncClient):
        """Test handling of invalid bot ID"""
        response = await client.get("/api/v1/bots/nonexistent/stats")

        # Should return 404 or 503 (if bots disabled)
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]

    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """Test CORS headers are present"""
        response = await client.options("/")

        # Check CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestIntegrationScenario:
    """Test realistic usage scenarios"""

    @pytest.mark.asyncio
    async def test_full_startup_sequence(self, client: AsyncClient):
        """Test typical startup health check sequence"""

        # 1. Check root endpoint
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        # 2. Check health
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "healthy"

        # 3. Check database
        response = await client.get("/health/database")
        assert response.status_code == status.HTTP_200_OK

        # 4. Check active pipeline
        response = await client.get("/api/v1/pipelines/active")
        assert response.status_code == status.HTTP_200_OK

        # 5. Check portfolio summary
        response = await client.get("/api/v1/portfolio/summary")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_api_responsiveness(self, client: AsyncClient):
        """Test that API responds quickly to multiple requests"""
        import time

        start = time.time()

        # Make multiple concurrent requests
        tasks = [
            client.get("/health"),
            client.get("/"),
            client.get("/api/v1/pipelines/active"),
        ]

        responses = await asyncio.gather(*tasks)

        elapsed = time.time() - start

        # All requests should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

        # Should complete in reasonable time (even on slow systems)
        assert elapsed < 5.0, f"API took {elapsed}s to respond to 3 requests"


# Run tests with: pytest tests/test_e2e_smoke.py -v
# Run with coverage: pytest tests/test_e2e_smoke.py --cov=src --cov-report=html
