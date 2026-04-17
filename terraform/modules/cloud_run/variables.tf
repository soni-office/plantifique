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

variable "firebase_tenant_id" {
  description = "GCIP tenant ID for this environment (Identity Platform)"
  type        = string
}

variable "want_to_use_rag" {
  description = "Enable RAG pipeline"
  type        = bool
  default     = false
}

variable "vertex_model" {
  description = "Vertex AI model name (e.g. gemini-2.5-flash)"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "phase4_gcs_bucket" {
  description = "GCS bucket name for Phase 4 video uploads (Vertex AI multimodal)"
  type        = string
  # No default — must be passed explicitly so it always matches the actual bucket name
}

variable "mock_sample_requests" {
  description = "Use mock sample request data instead of live TikTok API"
  type        = bool
  default     = false
}

variable "cache_default_ttl" {
  description = "Default Redis cache TTL in seconds"
  type        = number
  default     = 300
}

variable "timeout_seconds" {
  description = "Cloud Run request timeout in seconds (Phase 4 video analysis can take 60-120s)"
  type        = number
  default     = 600
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
  description = "Container memory limit (Phase 4 yt-dlp + video buffers need >= 4Gi)"
  type        = string
  default     = "4Gi"
}

variable "cpu" {
  description = "Container CPU limit"
  type        = string
  default     = "2"
}
