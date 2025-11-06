@echo off
REM Apply Binance Bot Schema to PostgreSQL Database
echo ========================================
echo Applying Binance Bot Schema
echo ========================================
echo.

cd /d "%~dp0.."

REM Try using the virtual environment Python
if exist "venv_binance\Scripts\python.exe" (
    echo Using venv_binance Python...
    venv_binance\Scripts\python.exe scripts\apply_bot_schema_direct.py
) else if exist "venv_binance\bin\python" (
    echo Using venv_binance Python (Unix-style)...
    venv_binance\bin\python scripts\apply_bot_schema_direct.py
) else (
    echo Using system Python...
    python scripts\apply_bot_schema_direct.py
)

echo.
pause
