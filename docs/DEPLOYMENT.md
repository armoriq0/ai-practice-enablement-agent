# GCP deployment

## Prerequisites

Install `gcloud`, Terraform 1.7+, Docker, and `curl`; select a billing-enabled project; authenticate with Application Default Credentials. Use Workload Identity Federation in CI.

```bash
export GCP_PROJECT_ID=your-project
export GCP_REGION=us-east1
export TF_STATE_BUCKET=$GCP_PROJECT_ID-armoriq-partner-tfstate
./scripts/bootstrap_gcp.sh
./scripts/configure_google_oauth.sh
./scripts/configure_secrets.sh
cp infra/terraform/environments/prod/backend.hcl.example infra/terraform/environments/prod/backend.hcl
cp infra/terraform/environments/prod/terraform.tfvars.example infra/terraform/environments/prod/terraform.tfvars
terraform -chdir=infra/terraform/environments/prod init -backend-config=backend.hcl
terraform -chdir=infra/terraform/environments/prod plan
terraform -chdir=infra/terraform/environments/prod apply
export DATABASE_PASSWORD='the same password used in DATABASE_URL'
./scripts/deploy.sh
```

Keep schedulers paused until OAuth, ArmorIQ production connectivity, migrations, policy validation, and smoke tests pass. Enabling a scheduler does not grant action authority. Configure Cloud Monitoring notification channels separately because recipients are organization-specific.

For production deployment approval, protect the GitHub `production` environment. The workflow uses OIDC federation and no service-account key.

