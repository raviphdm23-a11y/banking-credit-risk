# Flask Development Server Startup Script
# Usage: .\run_flask.ps1

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Banking Credit Risk Calculator - Flask Backend" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host ""

# Check if venv exists
$venvPath = Join-Path $ProjectRoot "venv310"
if (-not (Test-Path $venvPath)) {
    Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Yellow
    py -3.10 -m venv venv310
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "[✓] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[✓] Virtual environment already exists" -ForegroundColor Green
}

Write-Host ""

# Activate venv
Write-Host "[2/3] Activating virtual environment..." -ForegroundColor Yellow
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

# Set execution policy if needed
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -WarningAction SilentlyContinue

& $activateScript
Write-Host "[✓] Virtual environment activated" -ForegroundColor Green

Write-Host ""

# Install dependencies
Write-Host "[3/3] Installing/verifying dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt 2>$null
Write-Host "[✓] Dependencies installed" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting Flask Development Server" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Server will run on:     http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "📋 API Documentation:      http://127.0.0.1:5000/api/info" -ForegroundColor Green
Write-Host "❤️  Health Check:           http://127.0.0.1:5000/api/health" -ForegroundColor Green
Write-Host "🌐 Main Application:       http://127.0.0.1:5000/" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run Flask
python app.py
