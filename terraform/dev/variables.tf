variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "tiktok-ai-agent-488417"
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "image" {
  description = "Full Docker image URI to deploy (set by deploy.sh)"
  type        = string
  # Default is a placeholder used only for the very first terraform apply
  # before any real image has been built. deploy.sh will override this.
  default = "us-docker.pkg.dev/cloudrun/container/hello:latest"
}

variable "firebase_tenant_id" {
  description = "GCIP tenant ID for this environment (Identity Platform)"
  type        = string
  default     = "teampop-6fiht"
}

variable "internal_api_secret" {
  description = "Shared secret sent by Cloud Scheduler in x-internal-secret header. Must match the value stored in plantifique-dev-internal-api-secret in Secret Manager."
  type        = string
  sensitive   = true
}

variable "scheduler_cron_schedule" {
  description = "Cron schedule (UTC) for the process-samples job"
  type        = string
  default     = "0 * * * *"  # every hour on the hour
}