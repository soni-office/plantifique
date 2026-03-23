#!/usr/bin/env bash
# =============================================================================
# setup-infra.sh — Run Terraform to provision or update GCP infrastructure.
#
# Usage:
#   ./scripts/setup-infra.sh dev           # Plan + apply for dev
#   ./scripts/setup-infra.sh prod          # Plan + apply for prod (requires confirmation)
#   ./scripts/setup-infra.sh dev plan      # Plan only (no apply)
#
# Prerequisites:
#   1. Terraform >= 1.5 installed.
#   2. gcloud authenticated: gcloud auth application-default login
#   3. State bucket created once:
#        gcloud storage buckets create gs://tiktok-ai-agent-488417-tfstate \
#          --project=tiktok-ai-agent-488417 --location=us-central1 \
#          --uniform-bucket-level-access
# =============================================================================
set -euo pipefail

ENV="${1:-dev}"
ACTION="${2:-apply}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform/$ENV"

if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "ERROR: ENV must be 'dev' or 'prod'. Got: $ENV"
  exit 1
fi

if [[ ! -d "$TF_DIR" ]]; then
  echo "ERROR: Terraform directory not found: $TF_DIR"
  exit 1
fi

if [[ "$ENV" == "prod" && "$ACTION" == "apply" ]]; then
  echo ""
  echo "⚠️  You are applying Terraform changes to PRODUCTION."
  read -r -p "Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

echo ""
echo "============================================================"
echo "  Terraform $ACTION — ENV=$ENV"
echo "  Dir: $TF_DIR"
echo "============================================================"
echo ""

cd "$TF_DIR"

echo "[1/2] terraform init..."
terraform init -upgrade

if [[ "$ACTION" == "plan" ]]; then
  echo "[2/2] terraform plan..."
  terraform plan
else
  echo "[2/2] terraform apply..."
  terraform apply -auto-approve
  echo ""
  echo "✅ Infra apply complete. Outputs:"
  terraform output
fi
