resource "google_cloud_run_v2_service" "api" {
  name                = "plantifique-api-${var.env}"
  location            = var.region
  project             = var.project_id
  deletion_protection = false  # Allow Terraform to manage the full lifecycle

  template {
    service_account = var.service_account_email

    timeout = "${var.timeout_seconds}s"

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true  # Only charge for CPU during request processing
        startup_cpu_boost = true
      }

      # ---- Non-sensitive env vars (plain values) ----
      env { 
        name = "ENV"
        value = var.env 
      }
      env { 
        name = "GCP_PROJECT"
        value = var.project_id 
      }
      env { 
        name = "FIRESTORE_DATABASE"
        value = var.firestore_database 
      }
      env { 
        name = "FRONTEND_URL"
        value = var.frontend_url 
      }
      env { 
        name = "EXTRA_CORS_ORIGINS"
        value = var.extra_cors_origins 
      }
      env { 
        name = "REDIRECT_URI"
        value = var.redirect_uri 
      }
      env {
        name = "WANT_TO_USE_RAG"
        value = tostring(var.want_to_use_rag)
      }
      env {
        name  = "VERTEX_MODEL"
        value = var.vertex_model
      }
      env {
        name  = "FIREBASE_TENANT_ID"
        value = var.firebase_tenant_id
      }
      env {
        name  = "JWT_ALGORITHM"
        value = "HS256"
      }
      env {
        name  = "JWT_EXP_MINUTES"
        value = "60"
      }
      env {
        name  = "AUTH_URL"
        value = "https://auth.tiktok-shops.com/oauth/authorize"
      }
      env {
        name  = "TOKEN_URL"
        value = "https://auth.tiktok-shops.com/api/v2/token/get"
      }
      env {
        name  = "PHASE4_GCS_BUCKET"
        value = var.phase4_gcs_bucket
      }
      env {
        name  = "MOCK_SAMPLE_REQUESTS"
        value = tostring(var.mock_sample_requests)
      }
      env {
        name  = "CACHE_DEFAULT_TTL"
        value = tostring(var.cache_default_ttl)
      }
      env {
        name  = "BATCH_PROCESS_SAMPLE_REQUESTS_LIMIT"
        value = tostring(var.batch_process_limit)
      }

      # ---- Sensitive env vars (sourced from Secret Manager) ----
      env {
        name = "JWT_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["jwt_secret_key"]
            version = "latest"
          }
        }
      }

      env {
        name = "APP_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["app_key"]
            version = "latest"
          }
        }
      }

      env {
        name = "APP_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["app_secret"]
            version = "latest"
          }
        }
      }

      env {
        name = "FIREBASE_WEB_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["firebase_web_api_key"]
            version = "latest"
          }
        }
      }

      # env {
      #   name = "minmax_api_key"
      #   value_source {
      #     secret_key_ref {
      #       secret  = var.secret_ids["minmax_api_key"]
      #       version = "latest"
      #     }
      #   }
      # }

      env {
        name = "TIKTOK_TOKEN_ENCRYPTION_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["tiktok_encryption_key"]
            version = "latest"
          }
        }
      }

      env {
        name = "TIKAPI_KEY"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["tikapi_key"]
            version = "latest"
          }
        }
      }

      env {
        name = "REDIS_URL"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["redis_url"]
            version = "latest"
          }
        }
      }

      # Placeholder — will be populated with real value when Cloud Scheduler is integrated
      env {
        name = "INTERNAL_API_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.secret_ids["internal_api_secret"]
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    # Prevent Terraform from overwriting the image on every plan.
    # Image updates are done via deploy.sh (gcloud run deploy --image).
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Allow unauthenticated invocations — the app handles its own JWT auth.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
