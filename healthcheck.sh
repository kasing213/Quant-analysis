#!/bin/sh
# Railway healthcheck script that uses the PORT environment variable
curl -f http://localhost:${PORT:-8000}/health || exit 1
