#!/bin/bash

# Canonical launcher for Binance trading stack with consolidated logging.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Convert Unix path to Windows path for Python logging if on Windows/WSL
if [[ "$REPO_DIR" == /mnt/[a-z]/* ]]; then
    # Convert /mnt/d/path to D:/path for Windows Python (WSL format)
    REPO_DIR_WIN="$(echo "$REPO_DIR" | sed 's|^/mnt/\([a-z]\)/|\U\1:/|')"
elif [[ "$REPO_DIR" == /[a-z]/* ]]; then
    # Convert /d/path to D:/path for Windows Python (Git Bash format)
    REPO_DIR_WIN="$(echo "$REPO_DIR" | sed 's|^/\([a-z]\)/|\U\1:/|')"
else
    REPO_DIR_WIN="$REPO_DIR"
fi

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

create_virtualenv() {
    local target="$1"
    echo "Virtualenv '${target}' not found. Creating..."
    if command_exists python3; then
        python3 -m venv --without-pip "$target"
        echo "Installing pip manually to avoid ensurepip hang..."
        if [ -f "${target}/Scripts/python.exe" ]; then
            curl -s https://bootstrap.pypa.io/get-pip.py | "${target}/Scripts/python.exe"
        elif [ -f "${target}/bin/python" ]; then
            curl -s https://bootstrap.pypa.io/get-pip.py | "${target}/bin/python"
        fi
    else
        python -m venv --without-pip "$target"
        echo "Installing pip manually to avoid ensurepip hang..."
        if [ -f "${target}/Scripts/python.exe" ]; then
            curl -s https://bootstrap.pypa.io/get-pip.py | "${target}/Scripts/python.exe"
        elif [ -f "${target}/bin/python" ]; then
            curl -s https://bootstrap.pypa.io/get-pip.py | "${target}/bin/python"
        fi
    fi
}

ensure_redis() {
    # Check if Redis is disabled via environment variable
    if [ "${REDIS_ENABLED:-true}" = "false" ] || [ -z "${REDIS_HOST:-}" ]; then
        echo "Redis is disabled or not configured. Application will run without Redis."
        return
    fi

    if ! command_exists redis-cli; then
        echo "redis-cli not found; skipping Redis health check."
        return
    fi

    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        return
    fi

    if command_exists docker; then
        echo "Redis not detected. Launching docker container 'trading-redis'..."
        docker rm -f trading-redis >/dev/null 2>&1 || true
        if docker run -d -p "${REDIS_PORT}:6379" --name trading-redis redis:latest >/dev/null 2>&1; then
            sleep 2
        else
            echo "Docker launch failed. Please start Redis manually."
        fi
    else
        echo "Redis not running and Docker unavailable. Please start Redis and rerun this script."
    fi
}

create_log_config() {
    cat > "${UVICORN_LOG_CONFIG}" <<EOF
[loggers]
keys=root,uvicorn,uvicorn.error,uvicorn.access,binance

[handlers]
keys=consoleHandler,backendFileHandler,botFileHandler

[formatters]
keys=standard

[formatter_standard]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=standard
args=()

[handler_backendFileHandler]
class=FileHandler
level=INFO
formatter=standard
args=('${BACKEND_LOG_WIN}', 'a')

[handler_botFileHandler]
class=FileHandler
level=INFO
formatter=standard
args=('${BOT_LOG_WIN}', 'a')

[logger_root]
level=INFO
handlers=consoleHandler,backendFileHandler
qualname=root

[logger_uvicorn]
level=INFO
handlers=consoleHandler,backendFileHandler
propagate=0
qualname=uvicorn

[logger_uvicorn.error]
level=INFO
handlers=consoleHandler,backendFileHandler
propagate=0
qualname=uvicorn.error

[logger_uvicorn.access]
level=INFO
handlers=consoleHandler,backendFileHandler
propagate=0
qualname=uvicorn.access

[logger_binance]
level=INFO
handlers=botFileHandler
qualname=src.binance
propagate=1
EOF
}

run_backend() {
    echo ""
    echo "Backend listening on port ${APP_PORT}"
    echo "  Backend log : ${BACKEND_LOG}"
    echo "  Bot log     : ${BOT_LOG}"
    echo "-------------------------------------------"

    # Use API_HOST environment variable, default to 127.0.0.1 for security
    # Set API_HOST=0.0.0.0 in production/Docker environments only
    API_HOST="${API_HOST:-127.0.0.1}"

    PYTHONUNBUFFERED=1 "${PYTHON_BIN}" -m uvicorn src.api.main:app \
        --host "${API_HOST}" \
        --port "${APP_PORT}" \
        --reload \
        --log-config "${UVICORN_LOG_CONFIG}"
}

run_frontend() {
    echo ""
    echo "Frontend static server on port ${FRONTEND_PORT}"
    echo "  Frontend log: ${FRONTEND_LOG}"
    echo "-------------------------------------------"

    PYTHONUNBUFFERED=1 "${PYTHON_BIN}" -m http.server "${FRONTEND_PORT}" --directory frontend 2>&1 | tee -a "${FRONTEND_LOG}"
}

shutdown_processes() {
    echo ""
    echo "Stopping services..."
    for pid in "${PIDS[@]:-}"; do
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
            wait "${pid}" 2>/dev/null || true
        fi
    done
    echo "All services stopped."
}

# Load environment variables from .env file
load_env_file() {
    local env_file="${REPO_DIR}/.env"

    if [ ! -f "$env_file" ]; then
        echo "Warning: .env file not found at ${env_file}"
        echo "Using default environment variables only"
        return
    fi

    echo "Loading environment variables from .env file..."

    # Read .env file line by line and export variables
    # Skip comments (#) and empty lines
    # Handle both KEY=value and KEY="value" formats
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # Remove leading/trailing whitespace
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        # Skip if still empty after trimming
        [[ -z "$line" ]] && continue

        # Extract key and value
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"

            # Remove surrounding quotes if present
            value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")

            # Export the variable
            export "$key=$value"
        fi
    done < "$env_file"

    echo "✓ Environment variables loaded from .env"

    # Verify critical variables are set
    if [ -n "${DATABASE_URL:-}" ]; then
        echo "✓ DATABASE_URL is set"
    else
        echo "⚠ DATABASE_URL not found in .env file"
    fi
}

# Load .env file first (before defaults so .env takes precedence)
load_env_file

# Defaults (override via environment variables only if not already set)
export VENV_PATH="${VENV_PATH:-venv_binance}"
export APP_PORT="${APP_PORT:-8080}"  # Use 8080 locally to avoid conflict with Windows Device Portal on 8000
export REDIS_ENABLED="${REDIS_ENABLED:-false}"
export REDIS_HOST="${REDIS_HOST:-}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export BINANCE_TEST_MODE="${BINANCE_TEST_MODE:-true}"
export BINANCE_TESTNET="${BINANCE_TESTNET:-true}"
export BINANCE_ENABLE_MARKET_DATA="${BINANCE_ENABLE_MARKET_DATA:-true}"
export BINANCE_ENABLE_BOTS="${BINANCE_ENABLE_BOTS:-false}"
export ENABLE_DASHBOARD_FIXTURES="${ENABLE_DASHBOARD_FIXTURES:-true}"

LOG_DIR="${LOG_DIR:-${REPO_DIR}/logs}"
BACKEND_LOG="${BACKEND_LOG:-${LOG_DIR}/backend.log}"
BOT_LOG="${BOT_LOG:-${LOG_DIR}/bot.log}"
FRONTEND_LOG="${FRONTEND_LOG:-${LOG_DIR}/frontend.log}"
# Use relative path for uvicorn log config to avoid Windows/WSL path issues
UVICORN_LOG_CONFIG="${UVICORN_LOG_CONFIG:-logs/uvicorn-log.ini}"

# Use Windows-compatible paths for Python logging
BACKEND_LOG_WIN="${REPO_DIR_WIN}/logs/backend.log"
BOT_LOG_WIN="${REPO_DIR_WIN}/logs/bot.log"
START_FRONTEND="${START_FRONTEND:-true}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

mkdir -p "${LOG_DIR}"
touch "${BACKEND_LOG}" "${BOT_LOG}" "${FRONTEND_LOG}"
create_log_config

echo "Starting Binance Trading Stack"
echo "Repository:  ${REPO_DIR}"
echo "Virtualenv:  ${VENV_PATH}"
if [ "${REDIS_ENABLED}" = "true" ] && [ -n "${REDIS_HOST}" ]; then
    echo "Redis:       ${REDIS_HOST}:${REDIS_PORT}"
else
    echo "Redis:       Disabled (running without Redis)"
fi
echo "Logs dir:    ${LOG_DIR}"
echo "-------------------------------------------"

if [ ! -d "${VENV_PATH}" ]; then
    create_virtualenv "${VENV_PATH}"
fi

# Check for Windows-style (Scripts) or Unix-style (bin) virtualenv
if [ -f "${VENV_PATH}/Scripts/activate" ]; then
    ACTIVATE_SCRIPT="${VENV_PATH}/Scripts/activate"
    PYTHON_BIN="${VENV_PATH}/Scripts/python.exe"
elif [ -f "${VENV_PATH}/bin/activate" ]; then
    ACTIVATE_SCRIPT="${VENV_PATH}/bin/activate"
    PYTHON_BIN="${VENV_PATH}/bin/python"
else
    echo "Error: Could not find activate script in ${VENV_PATH}"
    exit 1
fi

echo "Activating virtualenv..."
# shellcheck disable=SC1090
source "${ACTIVATE_SCRIPT}"

# Verify we're using the correct Python
echo "Using Python: ${PYTHON_BIN}"
"${PYTHON_BIN}" --version

if [ "${SKIP_PIP_INSTALL:-0}" != "1" ]; then
    if [ ! -f "requirements/binance.txt" ]; then
        echo "requirements/binance.txt missing. Cannot continue."
        exit 1
    fi
    echo "Ensuring dependencies are installed..."
    "${PYTHON_BIN}" -m pip install --upgrade pip >/dev/null
    "${PYTHON_BIN}" -m pip install -r requirements/binance.txt >/dev/null
else
    echo "Skipping dependency install (SKIP_PIP_INSTALL=1)."
fi

ensure_redis

# Enhanced cleanup function for bot processes
cleanup_existing_processes() {
    echo "Cleaning up existing processes..."

    # Kill processes on API port
    if command_exists lsof && lsof -ti :"${APP_PORT}" >/dev/null 2>&1; then
        echo "Terminating processes on port ${APP_PORT}..."
        lsof -ti :"${APP_PORT}" | xargs kill -15 || true
        sleep 2
        # Force kill if still running
        lsof -ti :"${APP_PORT}" | xargs kill -9 || true
        sleep 1
    fi

    # Kill processes on frontend port
    if [ "${START_FRONTEND}" = "true" ] && command_exists lsof && lsof -ti :"${FRONTEND_PORT}" >/dev/null 2>&1; then
        echo "Terminating processes on port ${FRONTEND_PORT}..."
        lsof -ti :"${FRONTEND_PORT}" | xargs kill -15 || true
        sleep 2
        lsof -ti :"${FRONTEND_PORT}" | xargs kill -9 || true
        sleep 1
    fi

    # Kill any uvicorn/python processes that might be hanging
    if command_exists pgrep; then
        echo "Cleaning up any remaining uvicorn processes..."
        pgrep -f "uvicorn.*src.api.main" | xargs kill -15 2>/dev/null || true
        sleep 2
        pgrep -f "uvicorn.*src.api.main" | xargs kill -9 2>/dev/null || true

        echo "Cleaning up any remaining python bot processes..."
        pgrep -f "python.*trading.*bot" | xargs kill -15 2>/dev/null || true
        sleep 1
        pgrep -f "python.*trading.*bot" | xargs kill -9 2>/dev/null || true
    fi

    echo "Process cleanup completed."
}

cleanup_existing_processes

echo ""
echo "Backend endpoints:"
echo "  UI / Dashboard  : http://localhost:${APP_PORT}/"
echo "  API Docs        : http://localhost:${APP_PORT}/docs"
echo "  Health Check    : http://localhost:${APP_PORT}/health"
echo "  Bot API         : http://localhost:${APP_PORT}/api/v1/bots/"
if [ "${START_FRONTEND}" = "true" ]; then
    echo "Frontend static UI: http://localhost:${FRONTEND_PORT}/"
fi
echo "Press Ctrl+C to stop."
echo "-------------------------------------------"

PIDS=()
trap shutdown_processes INT TERM

run_backend &
PIDS+=("$!")

if [ "${START_FRONTEND}" = "true" ]; then
    run_frontend &
    PIDS+=("$!")
fi

set +e
wait -n "${PIDS[@]}"
EXIT_CODE=$?
set -e

shutdown_processes
exit "${EXIT_CODE}"
