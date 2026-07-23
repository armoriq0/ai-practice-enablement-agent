terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

locals {
  labels = {
    application = "armoriq-partner-agent"
    environment = var.environment
    managed_by  = "terraform"
  }
  secret_ids = toset([
    "OPENAI_API_KEY",
    "ARMORIQ_API_KEY",
    "ARMORIQ_BASE_URL",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "DATABASE_URL",
    "APPLICATION_SECRET",
    "OPTIONAL_SEARCH_PROVIDER_KEYS"
  ])
  queues = {
    discovery        = { rate = 2, concurrent = 2 }
    research         = { rate = 5, concurrent = 5 }
    enrichment       = { rate = 3, concurrent = 3 }
    generation       = { rate = 5, concurrent = 5 }
    google-workspace = { rate = 2, concurrent = 2 }
  }
  schedules = {
    daily-discovery      = { schedule = "0 8 * * *", path = "/api/v1/tasks/scheduled/discovery" }
    due-followups        = { schedule = "0 9 * * *", path = "/api/v1/tasks/scheduled/followups" }
    gmail-reply-sync     = { schedule = "*/15 * * * *", path = "/api/v1/tasks/scheduled/replies" }
    evidence-refresh     = { schedule = "0 3 * * *", path = "/api/v1/tasks/scheduled/evidence-refresh" }
    stale-account-review = { schedule = "0 7 * * 1", path = "/api/v1/tasks/scheduled/stale-accounts" }
    weekly-analytics     = { schedule = "0 7 * * 5", path = "/api/v1/tasks/scheduled/analytics" }
    monthly-cost-report  = { schedule = "0 7 1 * *", path = "/api/v1/tasks/scheduled/cost-report" }
  }
}

resource "google_service_account" "runtime" {
  account_id   = "${var.name}-${var.environment}-runtime"
  display_name = "ArmorIQ partner runtime (${var.environment})"
}

resource "google_service_account" "scheduler" {
  account_id   = "${var.name}-${var.environment}-scheduler"
  display_name = "ArmorIQ partner scheduler (${var.environment})"
}

resource "google_sql_database_instance" "postgres" {
  name                = "${var.name}-${var.environment}-postgres"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = var.deletion_protection
  settings {
    tier              = var.database_tier
    edition           = "ENTERPRISE"
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "04:00"
    }
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
    }
    user_labels = local.labels
  }
}

resource "google_sql_database" "application" {
  name     = "partner"
  instance = google_sql_database_instance.postgres.name
}

# Secret containers and versions are created out-of-band by configure_secrets.sh.
# This avoids putting any secret value in Terraform state.
data "google_secret_manager_secret" "runtime" {
  for_each  = local.secret_ids
  secret_id = lower(replace(each.value, "_", "-"))
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = local.secret_ids
  secret_id = data.google_secret_manager_secret.runtime[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_tasks_queue" "queues" {
  for_each = local.queues
  name     = "${each.key}-queue"
  location = var.region
  rate_limits {
    max_dispatches_per_second = each.value.rate
    max_concurrent_dispatches = each.value.concurrent
  }
  retry_config {
    max_attempts       = 8
    max_retry_duration = "3600s"
    min_backoff        = "5s"
    max_backoff        = "300s"
    max_doublings      = 5
  }
}

resource "google_cloud_run_v2_service" "backend" {
  name                = "${var.name}-${var.environment}-backend"
  location            = var.region
  deletion_protection = var.deletion_protection
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.runtime.email
    timeout         = "900s"
    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = 10
    }
    containers {
      image = var.backend_image
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
      ports {
        container_port = 8080
      }
      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 12
        http_get {
          path = "/health"
          port = 8080
        }
      }
      liveness_probe {
        timeout_seconds   = 3
        period_seconds    = 30
        failure_threshold = 3
        http_get {
          path = "/health"
          port = 8080
        }
      }
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "AUTONOMOUS_EXECUTION_ENABLED"
        value = "true"
      }
      env {
        name  = "ARMORIQ_FAIL_CLOSED"
        value = "true"
      }
      env {
        name  = "ARMORIQ_MODE"
        value = "remote"
      }
      env {
        name  = "MODEL_MODE"
        value = "openai"
      }
      env {
        name  = "OPENAI_MODEL"
        value = "gpt-5.6-sol"
      }
      dynamic "env" {
        for_each = local.secret_ids
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = data.google_secret_manager_secret.runtime[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
    vpc_access {
      connector = var.vpc_connector
      egress    = var.vpc_connector == null ? null : "PRIVATE_RANGES_ONLY"
    }
  }
  labels     = local.labels
  depends_on = [google_secret_manager_secret_iam_member.runtime]
}

resource "google_cloud_run_v2_service" "frontend" {
  name                = "${var.name}-${var.environment}-frontend"
  location            = var.region
  deletion_protection = var.deletion_protection
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.runtime.email
    scaling {
      max_instance_count = 10
    }
    containers {
      image = var.frontend_image
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      ports {
        container_port = 8080
      }
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }
  labels = local.labels
}

resource "google_cloud_run_v2_job" "daily_discovery" {
  name                = "${var.name}-${var.environment}-daily-discovery"
  location            = var.region
  deletion_protection = var.deletion_protection
  template {
    task_count = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "3600s"
      max_retries     = 1
      containers {
        image   = var.backend_image
        command = ["python", "-m", "app.worker"]
        resources {
          limits = { cpu = "2", memory = "2Gi" }
        }
        env {
          name  = "APP_ENV"
          value = var.environment
        }
        env {
          name  = "MODEL_MODE"
          value = "openai"
        }
        env {
          name  = "OPENAI_MODEL"
          value = "gpt-5.6-sol"
        }
        env {
          name  = "ARMORIQ_FAIL_CLOSED"
          value = "true"
        }
        env {
          name  = "ARMORIQ_MODE"
          value = "remote"
        }
        env {
          name  = "AUTONOMOUS_EXECUTION_ENABLED"
          value = "true"
        }
        env {
          name  = "BACKGROUND_WORKER_RUN_ONCE"
          value = "true"
        }
        dynamic "env" {
          for_each = local.secret_ids
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = data.google_secret_manager_secret.runtime[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres.connection_name]
        }
      }
      vpc_access {
        connector = var.vpc_connector
        egress    = var.vpc_connector == null ? null : "PRIVATE_RANGES_ONLY"
      }
    }
  }
  labels     = local.labels
  depends_on = [google_secret_manager_secret_iam_member.runtime]
}

resource "google_cloud_run_v2_job_iam_member" "daily_discovery_scheduler" {
  project  = var.project_id
  location = google_cloud_run_v2_job.daily_discovery.location
  name     = google_cloud_run_v2_job.daily_discovery.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "daily_discovery_job" {
  name             = "${var.name}-${var.environment}-daily-discovery-job"
  description      = "Runs continuous partner discovery once daily"
  schedule         = var.daily_discovery_schedule
  time_zone        = var.scheduler_time_zone
  attempt_deadline = "180s"
  paused           = !var.enable_schedulers
  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.daily_discovery.name}:run"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode("{}")
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "frontend_access" {
  for_each = toset(var.operator_members)
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_cloud_run_v2_service_iam_member" "backend_from_runtime" {
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service_iam_member" "backend_from_scheduler" {
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "jobs" {
  for_each         = var.enable_maintenance_schedulers ? local.schedules : {}
  name             = "${var.name}-${var.environment}-${each.key}"
  description      = "Triggers an ArmorIQ-authorized autonomous workflow; scheduler cannot authorize actions"
  schedule         = each.value.schedule
  time_zone        = "America/New_York"
  attempt_deadline = "300s"
  paused           = !var.enable_schedulers
  retry_config {
    retry_count          = 3
    min_backoff_duration = "10s"
    max_backoff_duration = "300s"
  }
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.backend.uri}${each.value.path}"
    headers     = { "Content-Type" = "application/json", "X-Workflow-Trigger" = "scheduler" }
    body        = base64encode(jsonencode({ trigger = each.key }))
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.backend.uri
    }
  }
}

resource "google_monitoring_alert_policy" "backend_errors" {
  display_name = "${var.name}-${var.environment}: backend 5xx responses"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run 5xx rate"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${google_cloud_run_v2_service.backend.name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
  documentation {
    content   = "Investigate backend errors. Disable autonomous execution or pause schedulers if authorization integrity is uncertain."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_dashboard" "operations" {
  dashboard_json = jsonencode({
    displayName = "${var.name}-${var.environment} operations"
    mosaicLayout = {
      columns = 12
      tiles = [{
        xPos = 0, yPos = 0, width = 12, height = 4
        widget = {
          title = "Backend requests"
          xyChart = { dataSets = [{
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.service_name=\"${google_cloud_run_v2_service.backend.name}\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE" }
            } }
            plotType = "LINE"
          }] }
        }
      }]
    }
  })
}
