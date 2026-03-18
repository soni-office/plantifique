variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "tiktok-ai-agent-488417"
}

variable "env" {
  description = "Environment name: dev or prod"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'."
  }
}

variable "secret_names" {
  description = "Map of logical name -> Secret Manager secret name suffix"
  type        = map(string)
  default = {
    jwt_secret_key            = "jwt-secret-key"
    app_key                   = "app-key"
    app_secret                = "app-secret"
    # minmax_api_key            = "minmax-api-key"
    tiktok_encryption_key     = "tiktok-encryption-key"
  }
}
