#!/bin/bash
# Complete dependency installer

echo "📦 Installing ALL dependencies..."
echo "This may take 2-3 minutes. Please wait..."
echo ""

source venv_api/bin/activate

# Install everything in one go
pip install --upgrade pip

echo "Installing packages..."
pip install \
    fastapi \
    uvicorn[standard] \
    pandas \
    numpy \
    websockets \
    redis \
    aiohttp \
    python-dotenv \
    backtrader \
    matplotlib \
    plotly \
    yfinance \
    scipy \
    statsmodels \
    psycopg2-binary \
    asyncpg \
    sqlalchemy \
    alembic \
    pydantic \
    pydantic-settings \
    requests \
    python-dateutil \
    pytz

echo ""
echo "✅ All dependencies installed!"
