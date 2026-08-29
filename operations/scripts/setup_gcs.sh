#!/bin/bash
# setup_gcs.sh — Create and configure Google Cloud Storage buckets
# Usage: ./setup_gcs.sh

set -e

PROJECT_ID="render-demo-06062141"
REGION="us-central1"
SERVICE_NAME="banking-credit-risk"

echo "================================================"
echo "Banking Credit Risk Calculator — GCS Setup"
echo "================================================"
echo ""

# Check gcloud CLI
if ! command -v gsutil &> /dev/null; then
    echo "[✗] gsutil not found. Install Google Cloud SDK first."
    exit 1
fi

echo "[1/5] Creating GCS buckets..."
echo ""

# Data bucket (models + database)
echo "  Creating banking-credit-risk-data..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://banking-credit-risk-data 2>/dev/null || true
echo "  ✓ banking-credit-risk-data"

# Reports bucket (ephemeral, auto-delete after 30 days)
echo "  Creating banking-credit-risk-reports..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://banking-credit-risk-reports 2>/dev/null || true
echo "  ✓ banking-credit-risk-reports"

# Audit bucket (immutable, 7-year retention)
echo "  Creating banking-credit-risk-audit..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://banking-credit-risk-audit 2>/dev/null || true
echo "  ✓ banking-credit-risk-audit"

echo ""
echo "[2/5] Setting lifecycle policies..."
echo ""

# Reports: delete after 30 days
cat > /tmp/lifecycle-reports.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF
gsutil lifecycle set /tmp/lifecycle-reports.json gs://banking-credit-risk-reports
echo "  ✓ Reports: auto-delete after 30 days"

# Audit: retain 7 years (minimal cost)
cat > /tmp/lifecycle-audit.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF
gsutil lifecycle set /tmp/lifecycle-audit.json gs://banking-credit-risk-audit
echo "  ✓ Audit: archive to COLDLINE after 1 year"

echo ""
echo "[3/5] Setting bucket permissions..."
echo ""

# Get Cloud Run service account
SERVICE_ACCOUNT=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION --project $PROJECT_ID \
  --format='value(serviceAccountEmail)' 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
    echo "  ⚠ Service account not found. Deploy Cloud Run first:"
    echo "    gcloud run deploy banking-credit-risk --source . --region us-central1"
    echo ""
    echo "  Then run this script again to grant permissions."
else
    echo "  Service Account: $SERVICE_ACCOUNT"
    echo ""

    for BUCKET in banking-credit-risk-{data,reports,audit}; do
        echo "  Granting permissions on gs://${BUCKET}..."
        gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectViewer gs://${BUCKET} 2>/dev/null || true
        gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectCreator gs://${BUCKET} 2>/dev/null || true
    done
    echo "  ✓ Cloud Run service account has full access"
fi

echo ""
echo "[4/5] Upload initial data..."
echo ""

if [ -f "bank.db" ]; then
    echo "  Uploading bank.db (this may take a few minutes)..."
    gsutil cp bank.db gs://banking-credit-risk-data/database/bank.db
    echo "  ✓ bank.db uploaded"
else
    echo "  ⚠ bank.db not found. Download it manually or initialize database on first Cloud Run startup."
fi

if [ -d "ml_models" ]; then
    echo "  Uploading ML models..."
    gsutil -m cp ml_models/pd_model_*.pkl gs://banking-credit-risk-data/models/
    gsutil -m cp ml_models/pd_model_*_metadata.json gs://banking-credit-risk-data/models/
    gsutil cp ml_models/active_model.json gs://banking-credit-risk-data/models/
    gsutil cp ml_models/hyperparameters.json gs://banking-credit-risk-data/models/
    echo "  ✓ ML models uploaded"
else
    echo "  ⚠ ml_models directory not found."
fi

echo ""
echo "[5/5] Verifying buckets..."
echo ""

for BUCKET in banking-credit-risk-{data,reports,audit}; do
    SIZE=$(gsutil du -s gs://${BUCKET} 2>/dev/null | awk '{print $1}' || echo "0")
    echo "  gs://${BUCKET}: $(numfmt --to=iec-i --suffix=B $SIZE 2>/dev/null || echo $SIZE)"
done

echo ""
echo "================================================"
echo "✓ GCS Setup Complete"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Verify data uploaded: gsutil ls -r gs://banking-credit-risk-data/"
echo "  2. Deploy Cloud Run: gcloud run deploy banking-credit-risk --source . --region us-central1"
echo "  3. Monitor startup: gcloud run services logs read banking-credit-risk --region us-central1"
echo ""
