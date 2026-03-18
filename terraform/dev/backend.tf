# Terraform remote state stored in GCS.
# Create this bucket ONCE manually before first terraform init:
#   gcloud storage buckets create gs://tiktok-ai-agent-488417-tfstate \
#     --project=tiktok-ai-agent-488417 \
#     --location=us-central1 \
#     --uniform-bucket-level-access

terraform {
  backend "gcs" {
    bucket = "tiktok-ai-agent-488417-tfstate"
    prefix = "plantifique/dev"
  }
}
