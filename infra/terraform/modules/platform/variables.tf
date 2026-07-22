variable "project_id" { type = string }
variable "region" { type = string }
variable "environment" { type = string }
variable "name" { type = string }
variable "backend_image" { type = string }
variable "frontend_image" { type = string }
variable "operator_members" {
  type    = list(string)
  default = []
}
variable "enable_schedulers" {
  type    = bool
  default = false
}
variable "daily_discovery_schedule" {
  type    = string
  default = "0 6 * * *"
}
variable "scheduler_time_zone" {
  type    = string
  default = "America/New_York"
}
variable "enable_maintenance_schedulers" {
  type    = bool
  default = false
}
variable "vpc_connector" {
  type    = string
  default = null
}
variable "database_tier" {
  type    = string
  default = "db-custom-1-3840"
}
variable "deletion_protection" {
  type    = bool
  default = true
}
