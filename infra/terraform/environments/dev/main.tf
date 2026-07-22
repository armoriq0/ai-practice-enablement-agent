terraform {
  required_version = ">= 1.7"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "platform" {
  source              = "../../modules/platform"
  project_id          = var.project_id
  region              = var.region
  environment         = "dev"
  name                = var.name
  backend_image       = var.backend_image
  frontend_image      = var.frontend_image
  operator_members    = var.operator_members
  enable_schedulers   = false
  deletion_protection = false
  database_tier       = "db-f1-micro"
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
variable "operator_members" {
  type    = list(string)
  default = []
}

output "backend_url" { value = module.platform.backend_url }
output "frontend_url" { value = module.platform.frontend_url }
output "oauth_redirect_uri" { value = module.platform.oauth_redirect_uri }
