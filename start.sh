#!/bin/bash

# Canonical launcher for Binance trading stack with consolidated logging.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Convert Unix path to Windows path for Python logging if on Windows/WSL
if [[ "$REPO_DIR" == /[a-z]/* ]]; then
    # Convert /d/path to D:/path for Windows Python
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
        python3 -m venv "$target"
    else
        python -m venv "$target"
    fi
}

ensure_redis() {
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

    PYTHONUNBUFFERED=1 python -m uvicorn src.api.main:app \
        --host 0.0.0.0 \
        --port "${APP_PORT}" \
        --reload \
        --log-config "${UVICORN_LOG_CONFIG}"
}

run_frontend() {
    echo ""
    echo "Frontend static server on port ${FRONTEND_PORT}"
    echo "  Frontend log: ${FRONTEND_LOG}"
    echo "-------------------------------------------"

    PYTHONUNBUFFERED=1 python -m http.server "${FRONTEND_PORT}" --directory frontend 2>&1 | tee -a "${FRONTEND_LOG}"
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

# Defaults (override via environment variables)
export VENV_PATH="${VENV_PATH:-venv_binance}"
export APP_PORT="${APP_PORT:-8000}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
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
UVICORN_LOG_CONFIG="${UVICORN_LOG_CONFIG:-${LOG_DIR}/uvicorn-log.ini}"

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
echo "Redis:       ${REDIS_HOST}:${REDIS_PORT}"
echo "Logs dir:    ${LOG_DIR}"
echo "-------------------------------------------"

if [ ! -d "${VENV_PATH}" ] || [ ! -f "${VENV_PATH}/bin/activate" ]; then
    create_virtualenv "${VENV_PATH}"
fi

echo "Activating virtualenv..."
# shellcheck disable=SC1090
source "${VENV_PATH}/bin/activate"

if [ "${SKIP_PIP_INSTALL:-0}" != "1" ]; then
    if [ ! -f "requirements/binance.txt" ]; then
        echo "requirements/binance.txt missing. Cannot continue."
        exit 1
    fi
    echo "Ensuring dependencies are installed..."
    python -m pip install --upgrade pip >/dev/null
    python -m pip install -r requirements/binance.txt >/dev/null
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
