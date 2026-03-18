output "service_url" {
  description = "The HTTPS URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

output "service_name" {
  description = "The Cloud Run service name"
  value       = google_cloud_run_v2_service.api.name
}
