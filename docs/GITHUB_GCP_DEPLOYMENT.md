# GitHub-to-GCP production deployment

Production deployment is CI-gated. A push to `main` runs `.github/workflows/ci.yml`; after CI succeeds, `.github/workflows/deploy.yml` builds commit-SHA-tagged images, applies Terraform, runs database migrations, and performs authenticated smoke checks. The dashboard and API run as private Cloud Run services. A Cloud Scheduler trigger starts the daily Cloud Run discovery job at 6:00 AM America/New_York.

## One-time GCP setup

Run these steps from a trusted administrator workstation. They require permission to enable APIs, create IAM resources, and configure Workload Identity Federation.

1. Create or select a billed GCP project and authenticate `gcloud`.
2. Set `GCP_PROJECT_ID` and `GCP_REGION`, then run `scripts/bootstrap_gcp.sh`.
3. Create a GitHub deployment service account and a Workload Identity Pool/provider restricted to the intended `OWNER/REPOSITORY` and `main` branch. Grant that identity permission to impersonate the deployment service account. Use short-lived Workload Identity Federation; do not create a JSON service-account key.
4. Grant the deployment service account the resource-management roles required by this Terraform stack: Cloud Build editor, Cloud Run admin, Cloud SQL admin, Cloud Scheduler admin, Cloud Tasks admin, Secret Manager admin, Monitoring editor, Service Account admin/user, Project IAM admin, Artifact Registry writer, and Storage object admin on the Terraform state bucket. Organization policy may require a narrower custom role.
5. Configure production secrets once with `scripts/configure_secrets.sh`. This creates Secret Manager versions without putting values in Terraform state.
6. Create the Google OAuth client using `scripts/configure_google_oauth.sh` and update the redirect URI secret after the first Terraform output is known.

## GitHub production environment

Create a GitHub environment named `production`. Add these environment variables:

| Name | Example |
| --- | --- |
| `GCP_PROJECT_ID` | `my-production-project` |
| `GCP_REGION` | `us-east1` |
| `TF_STATE_BUCKET` | `my-production-project-armoriq-partner-tfstate` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/123456789/locations/global/workloadIdentityPools/github/providers/github` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `github-deployer@my-production-project.iam.gserviceaccount.com` |
| `GCP_OPERATOR_MEMBERS_JSON` | `["user:operator@example.com"]` |

Add one GitHub environment secret:

- `DATABASE_PASSWORD`: the password used for the `partner` Cloud SQL user and the `DATABASE_URL` Secret Manager value.

Protect the `production` environment if deployments should require an operator approval. Leave it unprotected for fully automatic deploys after CI.

## Release behavior

1. Commit and push a change to `main`.
2. CI must pass.
3. GitHub authenticates to GCP using an OIDC token and Workload Identity Federation.
4. Cloud Build produces backend and frontend images tagged with the exact commit SHA.
5. Terraform updates Cloud Run, Cloud SQL/IAM infrastructure, and the daily discovery job.
6. Migrations run as a one-off Cloud Run Job.
7. Smoke checks verify the private backend and dashboard.

Failed CI does not deploy. Failed deploys leave the previous Cloud Run revision available for rollback. The daily job only processes missions whose policy has both `auto_execute=true` and `continuous=true`; every consequential action still requires ArmorIQ authorization.

To change the daily schedule, update `daily_discovery_schedule` in `infra/terraform/environments/prod/terraform.tfvars` or pass the corresponding Terraform variable. Scheduler times use America/New_York by default.
