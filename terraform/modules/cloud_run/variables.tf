variable "project_id" {
  description = "GCP project ID"
  type        = string
  default = "tiktok-ai-agent-488417"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "env" {
  description = "Environment: dev or prod"
  type        = string
  default     = "dev"
}

variable "image" {
  description = "Full Docker image path including tag"
  type        = string
}

variable "service_account_email" {
  description = "Cloud Run service account email"
  type        = string
}

variable "secret_ids" {
  description = "Map of logical name -> Secret Manager secret_id (from secrets module output)"
  type        = map(string)
}

# ---- Non-sensitive env vars ----
variable "frontend_url" {
  description = "Primary frontend URL for CORS and OAuth redirects"
  type        = string
}

variable "extra_cors_origins" {
  description = "Comma-separated extra CORS origins"
  type        = string
  default     = ""
}

variable "redirect_uri" {
  description = "TikTok OAuth redirect URI"
  type        = string
}

variable "firestore_database" {
  description = "Firestore database ID override (defaults to plantifique-pop-{env})"
  type        = string
  default     = ""
}

variable "want_to_use_rag" {
  description = "Enable RAG pipeline"
  type        = bool
  default     = false
}

variable "vertex_model" {
  description = "Vertex AI model name (e.g. gemini-2.0-flash-001)"
  type        = string
  default     = "gemini-2.5-flash"
}

# config for dev env - low
variable "min_instances" {
  description = "Minimum Cloud Run instances (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 2
}

variable "memory" {
  description = "Container memory limit"
  type        = string
  default     = "1Gi"
}

variable "cpu" {
  description = "Container CPU limit"
  type        = string
  default     = "1"
}
