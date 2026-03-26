variable "project_id" {
  type    = string
  default = "tiktok-ai-agent-488417"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "image" {
  description = "Full Docker image URI — set by deploy.sh"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello:latest"
}

variable "firebase_tenant_id" {
  description = "GCIP tenant ID for this environment (Identity Platform)"
  type        = string
  default     = "teampop-6fiht"
}
