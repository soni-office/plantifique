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
