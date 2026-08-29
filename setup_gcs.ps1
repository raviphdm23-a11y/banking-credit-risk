# setup_gcs.ps1 - Create and configure Google Cloud Storage buckets

$PROJECT_ID = "render-demo-06062141"
$REGION = "us-central1"
$SERVICE_NAME = "banking-credit-risk"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Banking Credit Risk Calculator - GCS Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloud) {
    Write-Host "[FAIL] gcloud CLI not found" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Creating GCS buckets..." -ForegroundColor Yellow
Write-Host ""

$buckets = @("banking-credit-risk-data", "banking-credit-risk-reports", "banking-credit-risk-audit")

foreach ($bucket in $buckets) {
    Write-Host "  Creating $bucket..." -NoNewline
    & gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$bucket 2>$null
    Write-Host " OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/5] Setting lifecycle policies..." -ForegroundColor Yellow
Write-Host ""

# Delete reports after 30 days
@"
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {"age": 30}
    }]
  }
}
"@ | Out-File -FilePath "$env:TEMP\lifecycle-reports.json" -Encoding utf8 -Force
& gsutil lifecycle set "$env:TEMP\lifecycle-reports.json" gs://banking-credit-risk-reports 2>$null
Write-Host "  OK Reports lifecycle: auto-delete after 30 days" -ForegroundColor Green

# Archive audit after 1 year
@"
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
      "condition": {"age": 365}
    }]
  }
}
"@ | Out-File -FilePath "$env:TEMP\lifecycle-audit.json" -Encoding utf8 -Force
& gsutil lifecycle set "$env:TEMP\lifecycle-audit.json" gs://banking-credit-risk-audit 2>$null
Write-Host "  OK Audit lifecycle: archive to COLDLINE after 1 year" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] Setting bucket permissions..." -ForegroundColor Yellow
Write-Host ""

try {
    $SERVICE_ACCOUNT = & gcloud run services describe $SERVICE_NAME --region $REGION --project $PROJECT_ID --format='value(serviceAccountEmail)' 2>$null
} catch {
    $SERVICE_ACCOUNT = ""
}

if ([string]::IsNullOrWhiteSpace($SERVICE_ACCOUNT)) {
    Write-Host "  WARNING: Service account not found. Deploy Cloud Run first." -ForegroundColor Yellow
    Write-Host "  After deployment, run: gcloud run deploy banking-credit-risk --source . --region us-central1" -ForegroundColor Gray
} else {
    Write-Host "  Service Account: $SERVICE_ACCOUNT" -ForegroundColor Cyan
    Write-Host ""
    foreach ($bucket in $buckets) {
        Write-Host "  Granting $bucket..." -NoNewline
        & gsutil iam ch "serviceAccount:$SERVICE_ACCOUNT`:roles/storage.objectViewer" gs://$bucket 2>$null
        & gsutil iam ch "serviceAccount:$SERVICE_ACCOUNT`:roles/storage.objectCreator" gs://$bucket 2>$null
        Write-Host " OK" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "[4/5] Uploading data..." -ForegroundColor Yellow
Write-Host ""

if (Test-Path "bank.db") {
    Write-Host "  Uploading bank.db..." -NoNewline
    & gsutil cp bank.db gs://banking-credit-risk-data/database/bank.db 2>$null
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host "  SKIP bank.db (not found locally)" -ForegroundColor Yellow
}

if (Test-Path "ml_models") {
    Write-Host "  Uploading ML models..." -NoNewline
    & gsutil -m cp ml_models/pd_model_*.pkl gs://banking-credit-risk-data/models/ 2>$null
    & gsutil -m cp ml_models/pd_model_*_metadata.json gs://banking-credit-risk-data/models/ 2>$null
    & gsutil cp ml_models/active_model.json gs://banking-credit-risk-data/models/ 2>$null
    & gsutil cp ml_models/hyperparameters.json gs://banking-credit-risk-data/models/ 2>$null
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host "  SKIP ml_models (not found)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[5/5] Verifying buckets..." -ForegroundColor Yellow
Write-Host ""

foreach ($bucket in $buckets) {
    try {
        $size = & gsutil du -s gs://$bucket 2>$null | Select-Object -First 1
        Write-Host "  gs://$bucket : $size" -ForegroundColor Gray
    } catch {
        Write-Host "  gs://$bucket : (checking...)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "OK GCS Setup Complete" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Deploy to Cloud Run" -ForegroundColor Cyan
Write-Host ""
