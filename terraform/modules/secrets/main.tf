# Creates Secret Manager secret containers for all sensitive env vars.
# Secret VALUES are NOT managed here — add them via bootstrap-secrets.sh after apply.

locals {
  # Full secret IDs: plantifique-dev-jwt-secret-key, plantifique-prod-app-key, etc.
  secrets = {
    for k, suffix in var.secret_names :
    k => "plantifique-${var.env}-${suffix}"
  }
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secrets
  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  labels = {
    env       = var.env
    managedby = "terraform"
  }
}

# NOTE: Secret-level IAM (secretmanager.secrets.setIamPolicy) requires
# roles/secretmanager.admin which the deployer may not have.
# The Cloud Run SA is granted roles/secretmanager.secretAccessor at the
# PROJECT level in dev/main.tf and prod/main.tf instead — this only
# requires roles/resourcemanager.projectIamAdmin.
