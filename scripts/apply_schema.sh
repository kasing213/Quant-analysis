#!/bin/bash
# Apply Binance Bot Schema to PostgreSQL Database

set -e

echo "========================================"
echo "Applying Binance Bot Schema"
echo "========================================"
echo ""

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Try using the virtual environment Python
if [ -f "venv_binance/bin/python" ]; then
    echo "Using venv_binance Python..."
    source venv_binance/bin/activate
    python scripts/apply_bot_schema_direct.py
elif [ -f "venv_binance/Scripts/python.exe" ]; then
    echo "Using venv_binance Python (Windows-style)..."
    venv_binance/Scripts/python.exe scripts/apply_bot_schema_direct.py
else
    echo "Using system Python..."
    python3 scripts/apply_bot_schema_direct.py
fi

echo ""
echo "✓ Done!"
