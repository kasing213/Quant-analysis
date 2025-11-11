#!/bin/sh
# Railway startup script with proper PORT handling
# This script ensures the app uses Railway's dynamic PORT environment variable

set -e

# Railway provides PORT dynamically, default to 8000 if not set
PORT=${PORT:-8000}

echo "=================================================="
echo "Starting Trading API on Railway"
echo "=================================================="
echo "PORT: $PORT"
echo "HOST: 0.0.0.0"
echo "Environment: ${ENVIRONMENT:-production}"
echo "=================================================="

# Check database connectivity before starting
if [ -n "$DATABASE_URL" ]; then
    echo "✓ DATABASE_URL is configured"
else
    echo "⚠ WARNING: DATABASE_URL not set"
fi

# Start uvicorn with proper port binding
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --access-log \
    --log-level info
