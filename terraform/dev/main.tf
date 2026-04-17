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
  env = "dev"
}

# ---------------------------------------------------------------------------
# Enable required GCP APIs
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry — shared between dev and prod, created once here.
# Uses lifecycle.prevent_destroy so a `terraform destroy` in dev doesn't
# remove the shared registry.
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "plantifique" {
  project       = var.project_id
  location      = var.region
  repository_id = "plantifique"
  format        = "DOCKER"
  description   = "Docker images for Plantifique API (shared dev/prod)"

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Service Account for the Cloud Run service
# ---------------------------------------------------------------------------
resource "google_service_account" "cloudrun_sa" {
  project      = var.project_id
  account_id   = "plantifique-api-${local.env}"
  display_name = "Plantifique API ${upper(local.env)} Cloud Run SA"
}

# ---- IAM: Firestore ----
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---- IAM: Vertex AI (Gemini / embeddings) ----
resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
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

# ---- IAM: Artifact Registry reader (project-level — only requires projectIAMAdmin) ----
resource "google_project_iam_member" "ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---------------------------------------------------------------------------
# GCS bucket for Phase 4 video uploads
# Videos are uploaded here before being passed to Vertex AI via gs:// URI,
# bypassing the inline request body size limit.
#
# If the bucket already exists (created in Console), import it first:
#   terraform import google_storage_bucket.phase4_videos tiktok-ai-agent-488417/plantifique-phase4-videos
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "phase4_videos" {
  project                     = var.project_id
  name                        = "plantifique-phase4-videos-${local.env}"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false  # prevent accidental deletion via terraform destroy

  labels = {
    env       = local.env
    purpose   = "phase4-video-analysis"
    managedby = "terraform"
  }

  # Auto-delete objects after 2 days — lifecycle rule is a safety net.
  # Videos are also deleted immediately after each analysis run in the code.
  lifecycle_rule {
    condition {
      age = 2  # days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---- IAM: Cloud Run SA can create and delete objects in the Phase 4 bucket ----
resource "google_storage_bucket_iam_member" "phase4_videos_admin" {
  bucket = google_storage_bucket.phase4_videos.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# ---------------------------------------------------------------------------
# Secret Manager secrets (containers only — values added via bootstrap-secrets.sh)
# ---------------------------------------------------------------------------
module "secrets" {
  source = "../modules/secrets"

  project_id = var.project_id
  env        = local.env

  depends_on = [
    google_project_service.apis,
    google_service_account.cloudrun_sa,
  ]
}

# ---------------------------------------------------------------------------
# Cloud Run service
# ---------------------------------------------------------------------------
module "cloud_run" {
  source = "../modules/cloud_run"

  project_id            = var.project_id
  region                = var.region
  env                   = local.env
  image                 = var.image
  service_account_email = google_service_account.cloudrun_sa.email
  secret_ids            = module.secrets.secret_ids

  # Non-sensitive env vars for dev
  frontend_url         = "https://tiktok-ai-agent-488417.web.app"
  extra_cors_origins   = "https://tiktok-ai-agent-488417.firebaseapp.com"
  redirect_uri         = "https://plantifique-api-dev-wtgyyixkpa-uc.a.run.app/auth/tiktokshop/callback"
  firebase_tenant_id   = var.firebase_tenant_id
  want_to_use_rag      = false
  mock_sample_requests = false
  phase4_gcs_bucket    = google_storage_bucket.phase4_videos.name
  # min_instances      = 0
  # max_instances      = 3
  # memory             = "1Gi"
  # cpu                = "1"

  depends_on = [
    google_project_service.apis,
    module.secrets,
    google_storage_bucket.phase4_videos,
    google_storage_bucket_iam_member.phase4_videos_admin,
  ]
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "service_url" {
  description = "Cloud Run service URL"
  value       = module.cloud_run.service_url
}

output "artifact_registry_repo" {
  description = "Docker image base path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.plantifique.repository_id}"
}

output "cloudrun_sa_email" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloudrun_sa.email
}

output "secret_ids" {
  description = "Secret Manager secret IDs (use bootstrap-secrets.sh to set values)"
  value       = module.secrets.secret_ids
}
