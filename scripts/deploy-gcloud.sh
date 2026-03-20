#!/bin/bash
# Deploy perpetual_predict to Google Cloud Run Jobs
# Usage: ./scripts/deploy-gcloud.sh

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="asia-northeast3"  # Seoul region for Binance API access
JOB_NAME="perpetual-predict-collector"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${JOB_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Perpetual Predict Cloud Run Deployment ===${NC}"

# Check prerequisites
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID environment variable not set${NC}"
    echo "Usage: GCP_PROJECT_ID=your-project-id ./scripts/deploy-gcloud.sh"
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}Not logged in to gcloud. Running 'gcloud auth login'...${NC}"
    gcloud auth login
fi

# Set project
echo -e "${GREEN}Setting project to ${PROJECT_ID}...${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo -e "${GREEN}Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    --quiet

# Build and push image
echo -e "${GREEN}Building and pushing Docker image...${NC}"
gcloud builds submit --tag "$IMAGE_NAME" .

# Create or update Cloud Run Job
echo -e "${GREEN}Creating/updating Cloud Run Job...${NC}"
if gcloud run jobs describe "$JOB_NAME" --region="$REGION" &> /dev/null; then
    echo "Updating existing job..."
    gcloud run jobs update "$JOB_NAME" \
        --image "$IMAGE_NAME" \
        --region "$REGION" \
        --task-timeout 10m \
        --max-retries 1 \
        --set-env-vars "DISCORD_ENABLED=true" \
        --set-secrets "DISCORD_WEBHOOK_URL=discord-webhook-url:latest" \
        --quiet
else
    echo "Creating new job..."
    gcloud run jobs create "$JOB_NAME" \
        --image "$IMAGE_NAME" \
        --region "$REGION" \
        --task-timeout 10m \
        --max-retries 1 \
        --set-env-vars "DISCORD_ENABLED=true" \
        --quiet

    echo -e "${YELLOW}Note: Discord webhook secret not set yet.${NC}"
    echo "Run this after creating the secret:"
    echo "  gcloud run jobs update $JOB_NAME --region $REGION --set-secrets 'DISCORD_WEBHOOK_URL=discord-webhook-url:latest'"
fi

# Create Cloud Scheduler job
SCHEDULER_JOB_NAME="${JOB_NAME}-scheduler"
echo -e "${GREEN}Creating/updating Cloud Scheduler...${NC}"

# Get service account for Cloud Run invoker
SERVICE_ACCOUNT="$(gcloud iam service-accounts list --filter='displayName:Compute Engine default' --format='value(email)' | head -1)"

if gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location="$REGION" &> /dev/null; then
    echo "Updating existing scheduler..."
    gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" \
        --location "$REGION" \
        --schedule "1 0,4,8,12,16,20 * * *" \
        --time-zone "UTC" \
        --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method POST \
        --oauth-service-account-email "$SERVICE_ACCOUNT" \
        --quiet
else
    echo "Creating new scheduler..."
    gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
        --location "$REGION" \
        --schedule "1 0,4,8,12,16,20 * * *" \
        --time-zone "UTC" \
        --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method POST \
        --oauth-service-account-email "$SERVICE_ACCOUNT" \
        --quiet
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Cloud Run Job: $JOB_NAME"
echo "Region: $REGION"
echo "Schedule: Every 4 hours at :01 (UTC)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Create Discord webhook secret:"
echo "   echo -n 'YOUR_DISCORD_WEBHOOK_URL' | gcloud secrets create discord-webhook-url --data-file=-"
echo ""
echo "2. Grant Cloud Run access to secret:"
echo "   gcloud secrets add-iam-policy-binding discord-webhook-url \\"
echo "     --member='serviceAccount:${SERVICE_ACCOUNT}' \\"
echo "     --role='roles/secretmanager.secretAccessor'"
echo ""
echo "3. Update job with secret:"
echo "   gcloud run jobs update $JOB_NAME --region $REGION --set-secrets 'DISCORD_WEBHOOK_URL=discord-webhook-url:latest'"
echo ""
echo "4. Test run manually:"
echo "   gcloud run jobs execute $JOB_NAME --region $REGION"
echo ""
echo "5. View logs:"
echo "   gcloud run jobs executions list --job $JOB_NAME --region $REGION"
