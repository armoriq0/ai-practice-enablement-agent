output "backend_url" { value = google_cloud_run_v2_service.backend.uri }
output "frontend_url" { value = google_cloud_run_v2_service.frontend.uri }
output "database_connection_name" { value = google_sql_database_instance.postgres.connection_name }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "oauth_redirect_uri" { value = "${google_cloud_run_v2_service.backend.uri}/api/v1/auth/google/callback" }
output "queue_names" { value = [for queue in google_cloud_tasks_queue.queues : queue.name] }

