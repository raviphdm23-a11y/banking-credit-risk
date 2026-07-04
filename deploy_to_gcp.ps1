# GCP App Engine Deployment Script
# Usage: .\deploy_to_gcp.ps1 [-ProjectId <your-gcp-project-id>]

param(
    [string]$ProjectId = ""
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Banking Credit Risk Calculator - GCP Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host ""

# [1] Check if gcloud CLI is installed
Write-Host "[1/5] Checking gcloud CLI installation..." -ForegroundColor Yellow
$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue

if (-not $gcloud) {
    Write-Host "[✗] gcloud CLI not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install gcloud SDK from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    Write-Host "After installation, restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}
Write-Host "[✓] gcloud CLI found at: $($gcloud.Source)" -ForegroundColor Green
Write-Host ""

# [2] Check gcloud authentication
Write-Host "[2/5] Checking gcloud authentication..." -ForegroundColor Yellow
$authList = & gcloud auth list 2>$null | Select-String "ACTIVE"

if (-not $authList) {
    Write-Host "[⚠] No active gcloud account. Opening login..." -ForegroundColor Yellow
    Write-Host ""
    & gcloud auth login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[✗] Authentication failed" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}
Write-Host "[✓] gcloud authenticated" -ForegroundColor Green
Write-Host ""

# [3] Set/Verify GCP Project ID
Write-Host "[3/5] Setting GCP Project ID..." -ForegroundColor Yellow

if ([string]::IsNullOrWhiteSpace($ProjectId)) {
    # Get current project
    $currentProject = & gcloud config get-value project 2>$null

    if ([string]::IsNullOrWhiteSpace($currentProject)) {
        Write-Host "[⚠] No GCP project configured" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Enter your GCP Project ID (e.g., my-credit-risk-project): " -ForegroundColor Cyan -NoNewline
        $ProjectId = Read-Host

        if ([string]::IsNullOrWhiteSpace($ProjectId)) {
            Write-Host "[✗] Project ID is required" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Current project: $currentProject" -ForegroundColor Cyan
        Write-Host "Use this project? (Y/n): " -ForegroundColor Yellow -NoNewline
        $response = Read-Host

        if ($response -eq 'n' -or $response -eq 'N') {
            Write-Host "Enter new GCP Project ID: " -ForegroundColor Cyan -NoNewline
            $ProjectId = Read-Host
            if ([string]::IsNullOrWhiteSpace($ProjectId)) {
                Write-Host "[✗] Project ID is required" -ForegroundColor Red
                exit 1
            }
        } else {
            $ProjectId = $currentProject
        }
    }
}

# Set the project
& gcloud config set project $ProjectId 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "[✗] Failed to set GCP project: $ProjectId" -ForegroundColor Red
    exit 1
}

Write-Host "[✓] GCP Project ID set to: $ProjectId" -ForegroundColor Green
Write-Host ""

# [4] Verify app.yaml exists
Write-Host "[4/5] Verifying deployment configuration..." -ForegroundColor Yellow

$appYamlPath = Join-Path $ProjectRoot "app.yaml"
if (-not (Test-Path $appYamlPath)) {
    Write-Host "[✗] app.yaml not found at: $appYamlPath" -ForegroundColor Red
    exit 1
}

$gcloudignorePath = Join-Path $ProjectRoot ".gcloudignore"
if (-not (Test-Path $gcloudignorePath)) {
    Write-Host "[⚠] .gcloudignore not found (optional)" -ForegroundColor Yellow
} else {
    Write-Host "[✓] app.yaml and .gcloudignore found" -ForegroundColor Green
}

Write-Host ""

# [5] Display deployment summary
Write-Host "[5/5] Deployment Summary" -ForegroundColor Yellow
Write-Host "────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "Project ID:        $ProjectId" -ForegroundColor Cyan
Write-Host "Service Name:      default" -ForegroundColor Cyan
Write-Host "Runtime:           Python 3.10" -ForegroundColor Cyan
Write-Host "Region:            (auto-selected by GCP)" -ForegroundColor Cyan
Write-Host "────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ""

# Confirm before deployment
Write-Host "Ready to deploy? (Y/n): " -ForegroundColor Yellow -NoNewline
$confirm = Read-Host

if ($confirm -eq 'n' -or $confirm -eq 'N') {
    Write-Host "[✗] Deployment cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting GCP App Engine Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Run deployment
& gcloud app deploy --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "Deployment Successful!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""

    # Get the deployed URL
    $appUrl = & gcloud app browse --no-launch 2>$null
    if ($appUrl) {
        Write-Host "🌐 Application URL: $appUrl" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  Run 'gcloud app browse' to open your application" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Yellow
    Write-Host "  View logs:      gcloud app logs read -f" -ForegroundColor Gray
    Write-Host "  Open app:       gcloud app browse" -ForegroundColor Gray
    Write-Host "  View versions:  gcloud app versions list" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "Deployment Failed" -ForegroundColor Red
    Write-Host "================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error output above and fix any issues." -ForegroundColor Yellow
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  • Missing dependencies in requirements.txt" -ForegroundColor Gray
    Write-Host "  • Invalid app.yaml configuration" -ForegroundColor Gray
    Write-Host "  • Insufficient GCP permissions" -ForegroundColor Gray
    Write-Host ""
    exit 1
}
