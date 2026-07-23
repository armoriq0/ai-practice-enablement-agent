terraform {
  required_version = ">= 1.7"
  backend "gcs" {}
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "platform" {
  source                   = "../../modules/platform"
  project_id               = var.project_id
  region                   = var.region
  environment              = "prod"
  name                     = var.name
  backend_image            = var.backend_image
  frontend_image           = var.frontend_image
  operator_members         = var.operator_members
  enable_schedulers        = var.enable_schedulers
  daily_discovery_schedule = var.daily_discovery_schedule
  deletion_protection      = false
  database_tier            = var.database_tier
  vpc_connector            = var.vpc_connector
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-east1"
}
variable "name" {
  type    = string
  default = "armoriq-partner"
}
variable "backend_image" { type = string }
variable "frontend_image" { type = string }
variable "operator_members" { type = list(string) }
variable "enable_schedulers" {
  type    = bool
  default = false
}
variable "daily_discovery_schedule" {
  type    = string
  default = "0 6 * * *"
}
variable "database_tier" {
  type    = string
  default = "db-custom-1-3840"
}
variable "vpc_connector" {
  type    = string
  default = null
}

output "backend_url" { value = module.platform.backend_url }
output "frontend_url" { value = module.platform.frontend_url }
output "oauth_redirect_uri" { value = module.platform.oauth_redirect_uri }
output "database_connection_name" { value = module.platform.database_connection_name }
