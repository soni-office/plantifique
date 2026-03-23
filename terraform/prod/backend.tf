terraform {
  backend "gcs" {
    bucket = "tiktok-ai-agent-488417-tfstate"
    prefix = "plantifique/prod"
  }
}
