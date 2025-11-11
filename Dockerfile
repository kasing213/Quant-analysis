FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements/requirements.txt .
COPY requirements/requirements_postgresql.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_postgresql.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser frontend/ ./frontend/
COPY --chown=appuser:appuser healthcheck.sh ./healthcheck.sh
COPY --chown=appuser:appuser start-railway.sh ./start-railway.sh

# Make scripts executable
RUN chmod +x /app/healthcheck.sh /app/start-railway.sh

# Switch to non-root user
USER appuser

# Health check - uses PORT env var that Railway provides via healthcheck script
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/app/healthcheck.sh"]

# Expose port (Railway will override this with $PORT)
EXPOSE 8000

# Use production ASGI server via startup script
# The start-railway.sh script properly handles Railway's dynamic PORT variable
CMD ["/app/start-railway.sh"]