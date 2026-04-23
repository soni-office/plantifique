#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Build, push, and deploy the Plantifique API to Cloud Run.
#
# Usage:
#   ./scripts/deploy.sh dev          # Deploy to dev (default)
#   ./scripts/deploy.sh prod         # Deploy to prod (requires confirmation)
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated:
#        gcloud auth login
#        gcloud auth configure-docker us-central1-docker.pkg.dev
#   2. Terraform infra already applied (run scripts/setup-infra.sh first).
#   3. Secrets populated in Secret Manager (run scripts/bootstrap-secrets.sh first).
#   4. Docker daemon running.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV="${1:-dev}"
VERTEX_MODEL="${2:-gemini-2.5-flash}"
FIREBASE_TENANT_ID="teampop-6fiht"
PROJECT_ID="tiktok-ai-agent-488417"
REGION="us-central1"
REPO="plantifique"
IMAGE_BASE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/api"
SERVICE_NAME="plantifique-api-$ENV"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)
IMAGE_TAG="$ENV-$GIT_SHA"
IMAGE="$IMAGE_BASE:$IMAGE_TAG"

# Also tag as env-latest for easy reference
IMAGE_LATEST="$IMAGE_BASE:$ENV-latest"

# ---------------------------------------------------------------------------
# Validate environment
# ---------------------------------------------------------------------------
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "ERROR: ENV must be 'dev' or 'prod'. Got: $ENV"
  exit 1
fi

if [[ "$ENV" == "prod" ]]; then
  echo ""
  echo "⚠️  You are deploying to PRODUCTION."
  read -r -p "Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

echo ""
echo "============================================================"
echo "  Deploying: $SERVICE_NAME"
echo "  Image:     $IMAGE"
echo "  Project:   $PROJECT_ID"
echo "  Region:    $REGION"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Ensure Docker is authenticated with Artifact Registry
# ---------------------------------------------------------------------------
echo "[1/4] Configuring Docker auth for Artifact Registry..."
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# ---------------------------------------------------------------------------
# 2. Build Docker image
# ---------------------------------------------------------------------------
echo "[2/4] Building Docker image..."
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker build \
  --platform linux/amd64 \
  -t "$IMAGE" \
  -t "$IMAGE_LATEST" \
  "$REPO_ROOT"

# ---------------------------------------------------------------------------
# 3. Push to Artifact Registry
# ---------------------------------------------------------------------------
echo "[3/4] Pushing image to Artifact Registry..."
docker push "$IMAGE"
docker push "$IMAGE_LATEST"

# ---------------------------------------------------------------------------
# 4. Deploy to Cloud Run
# ---------------------------------------------------------------------------
echo "[4/4] Deploying to Cloud Run ($SERVICE_NAME)..."

# Secret Manager refs (same names used in Terraform)
SECRETS="JWT_SECRET_KEY=plantifique-${ENV}-jwt-secret-key:latest,\
APP_KEY=plantifique-${ENV}-app-key:latest,\
APP_SECRET=plantifique-${ENV}-app-secret:latest,\
TIKTOK_TOKEN_ENCRYPTION_KEY=plantifique-${ENV}-tiktok-encryption-key:latest,\
FIREBASE_WEB_API_KEY=plantifique-${ENV}-firebase-web-api-key:latest,\
TIKAPI_KEY=plantifique-${ENV}-tikapi-key:latest,\
REDIS_URL=plantifique-${ENV}-redis-url:latest,\
INTERNAL_API_SECRET=plantifique-${ENV}-internal-api-secret:latest"

# Non-sensitive env vars (env-specific)
if [[ "$ENV" == "dev" ]]; then
  FRONTEND_URL="https://tiktok-ai-agent-488417.web.app"
  EXTRA_CORS_ORIGINS="https://tiktok-ai-agent-488417.firebaseapp.com"
  REDIRECT_URI="https://$SERVICE_NAME-$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null | sed 's|https://||' || echo 'placeholder')/auth/tiktokshop/callback"
  WANT_TO_USE_RAG="true"
  MIN_INSTANCES=0
  MAX_INSTANCES=2
  MEMORY="4Gi"
  CPU="2"
else
  FRONTEND_URL="https://tiktok-ai-agent-488417.web.app"
  EXTRA_CORS_ORIGINS="https://tiktok-ai-agent-488417.firebaseapp.com"
  REDIRECT_URI="https://$SERVICE_NAME-$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null | sed 's|https://||' || echo 'placeholder')/auth/tiktokshop/callback"
  WANT_TO_USE_RAG="true"
  MIN_INSTANCES=1
  MAX_INSTANCES=10
  MEMORY="2Gi"
  CPU="2"
fi

ENV_VARS="ENV=$ENV,\
GCP_PROJECT=$PROJECT_ID,\
FRONTEND_URL=$FRONTEND_URL,\
EXTRA_CORS_ORIGINS=$EXTRA_CORS_ORIGINS,\
REDIRECT_URI=$REDIRECT_URI,\
WANT_TO_USE_RAG=$WANT_TO_USE_RAG,\
JWT_ALGORITHM=HS256,\
JWT_EXP_MINUTES=60,\
AUTH_URL=https://auth.tiktok-shops.com/oauth/authorize,\
TOKEN_URL=https://auth.tiktok-shops.com/api/v2/token/get,\
VERTEX_MODEL=$VERTEX_MODEL,\
FIREBASE_TENANT_ID=$FIREBASE_TENANT_ID,\
BATCH_PROCESS_SAMPLE_REQUESTS_LIMIT=5"

gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --service-account="plantifique-api-${ENV}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-secrets="$SECRETS" \
  --set-env-vars="$ENV_VARS" \
  --allow-unauthenticated \
  --min-instances="$MIN_INSTANCES" \
  --max-instances="$MAX_INSTANCES" \
  --memory="$MEMORY" \
  --cpu="$CPU" \
  --port=8080 \
  --quiet

echo ""
echo "============================================================"
echo "  ✅ Deploy complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format='value(status.url)')
echo "  URL: $SERVICE_URL"
echo "  Image: $IMAGE"
echo "============================================================"
