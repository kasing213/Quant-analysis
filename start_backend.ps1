# Start Backend Server
Write-Host "Starting Backend API Server on port 8000..." -ForegroundColor Green

$env:PYTHONPATH = "$PSScriptRoot"

# Start the server
& "$PSScriptRoot\venv_api\Scripts\python.exe" -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Keep window open on error
if ($LASTEXITCODE -ne 0) {
    Write-Host "Server failed to start. Press any key to exit..." -ForegroundColor Red
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
