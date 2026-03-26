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