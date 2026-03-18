#!/usr/bin/env bash
# =============================================================================
# bootstrap-secrets.sh — Populate Secret Manager with actual secret values.
#
# Run this ONCE after `terraform apply` has created the secret containers.
# It reads values from your local .env.dev or .env.prod file and pushes
# them as secret versions to Secret Manager.
#
# Usage:
#   ./scripts/bootstrap-secrets.sh dev    # Populate dev secrets from .env.dev
#   ./scripts/bootstrap-secrets.sh prod   # Populate prod secrets from .env.prod
#
# Prerequisites:
#   - gcloud CLI authenticated with sufficient permissions (roles/secretmanager.admin)
#   - Terraform already applied (secret containers must exist)
#   - .env.dev / .env.prod populated with real values
# =============================================================================
set -euo pipefail

ENV="${1:-dev}"
PROJECT_ID="tiktok-ai-agent-488417"
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env.$ENV"

if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "ERROR: ENV must be 'dev' or 'prod'. Got: $ENV"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Create it from .env.example first."
  exit 1
fi

echo "============================================================"
echo "  Bootstrapping Secret Manager secrets for ENV=$ENV"
echo "  Reading values from: $ENV_FILE"
echo "  GCP Project: $PROJECT_ID"
echo "============================================================"
echo ""

# Helper: read a single key from the env file
get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2-
}

# Push one secret: <secret-id> <env-key>
push_secret() {
  local secret_id="$1"
  local env_key="$2"
  local value
  value="$(get_env_value "$env_key")"

  if [[ -z "$value" ]]; then
    echo "  SKIP: $secret_id — '$env_key' not set in $ENV_FILE"
    return
  fi

  echo "  -> Setting $secret_id ..."
  echo -n "$value" | gcloud secrets versions add "$secret_id" \
    --project="$PROJECT_ID" \
    --data-file=- \
    --quiet
  echo "     Done"
}

push_secret "plantifique-${ENV}-jwt-secret-key"      "JWT_SECRET_KEY"
push_secret "plantifique-${ENV}-app-key"              "APP_KEY"
push_secret "plantifique-${ENV}-app-secret"           "APP_SECRET"
push_secret "plantifique-${ENV}-tiktok-encryption-key" "TIKTOK_TOKEN_ENCRYPTION_KEY"

echo ""
echo "============================================================"
echo "  Secret bootstrap complete for ENV=$ENV"
echo "  Re-run anytime to rotate a secret (adds a new version)."
echo "============================================================"
