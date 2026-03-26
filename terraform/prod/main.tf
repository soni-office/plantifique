terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  env = "prod"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "cloudrun_sa" {
  project      = var.project_id
  account_id   = "plantifique-api-${local.env}"
  display_name = "Plantifique API ${upper(local.env)} Cloud Run SA"
}

resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---- IAM: Artifact Registry reader (project-level — only requires projectIAMAdmin) ----
resource "google_project_iam_member" "ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---- IAM: Identity Toolkit (required for Firebase Admin SDK token verification) ----
resource "google_project_iam_member" "identity_toolkit" {
  project = var.project_id
  role    = "roles/identitytoolkit.admin"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---- IAM: Secret Manager accessor (project-level — only requires projectIAMAdmin) ----
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

module "secrets" {
  source = "../modules/secrets"

  project_id = var.project_id
  env        = local.env

  depends_on = [
    google_project_service.apis,
    google_service_account.cloudrun_sa,
  ]
}

module "cloud_run" {
  source = "../modules/cloud_run"

  project_id            = var.project_id
  region                = var.region
  env                   = local.env
  image                 = var.image
  service_account_email = google_service_account.cloudrun_sa.email
  secret_ids            = module.secrets.secret_ids

  # Prod-specific non-sensitive values
  frontend_url       = "https://tiktok-ai-agent-488417.web.app"
  extra_cors_origins = "https://tiktok-ai-agent-488417.firebaseapp.com"
  # Update redirect_uri after first prod deploy (Cloud Run URL is known then)
  redirect_uri       = "https://plantifique-api-prod-placeholder.a.run.app/auth/tiktokshop/callback"
  firebase_tenant_id = var.firebase_tenant_id
  want_to_use_rag    = true
  min_instances   = 1    # Keep warm in prod
  max_instances   = 10
  memory          = "2Gi"
  cpu             = "2"

  depends_on = [
    google_project_service.apis,
    module.secrets,
  ]
}

output "service_url"        { value = module.cloud_run.service_url }
output "cloudrun_sa_email"  { value = google_service_account.cloudrun_sa.email }
output "secret_ids"         { value = module.secrets.secret_ids }
