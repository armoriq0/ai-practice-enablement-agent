#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${DATABASE_PASSWORD:?Set DATABASE_PASSWORD to the same value used in DATABASE_URL}"
GCP_REGION="${GCP_REGION:-us-east1}"
APP_NAME="${APP_NAME:-armoriq-partner}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
REPOSITORY="${ARTIFACT_REPOSITORY:-armoriq-partner}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
TF_DIR="infra/terraform/environments/${ENVIRONMENT}"
TF_STATE_BUCKET="${TF_STATE_BUCKET:-${GCP_PROJECT_ID}-armoriq-partner-tfstate}"

for command in gcloud terraform curl; do command -v "${command}" >/dev/null || { echo "${command} is required" >&2; exit 1; }; done
gcloud auth print-access-token >/dev/null

BACKEND_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPOSITORY}/backend:${TAG}"
FRONTEND_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPOSITORY}/frontend:${TAG}"
gcloud builds submit --config cloudbuild.yaml \
  --substitutions "_REGION=${GCP_REGION},_REPOSITORY=${REPOSITORY},_TAG=${TAG}" .

terraform -chdir="${TF_DIR}" init -backend-config="bucket=${TF_STATE_BUCKET}" -backend-config="prefix=${ENVIRONMENT}"

# Cloud Run connects to the database during application startup. Provision the
# database and synchronize its out-of-band password before creating a revision.
terraform -chdir="${TF_DIR}" apply \
  -target="module.platform.google_sql_database.application" \
  -var="project_id=${GCP_PROJECT_ID}" -var="region=${GCP_REGION}" \
  -var="backend_image=${BACKEND_IMAGE}" -var="frontend_image=${FRONTEND_IMAGE}" \
  -var="enable_schedulers=false"

INSTANCE="${APP_NAME}-${ENVIRONMENT}-postgres"
if gcloud sql users list --instance "${INSTANCE}" --format='value(name)' | grep -qx partner; then
  gcloud sql users set-password partner --instance "${INSTANCE}" --password "${DATABASE_PASSWORD}"
else
  gcloud sql users create partner --instance "${INSTANCE}" --password "${DATABASE_PASSWORD}"
fi

terraform -chdir="${TF_DIR}" apply \
  -var="project_id=${GCP_PROJECT_ID}" -var="region=${GCP_REGION}" \
  -var="backend_image=${BACKEND_IMAGE}" -var="frontend_image=${FRONTEND_IMAGE}" \
  -var="enable_schedulers=${ENABLE_SCHEDULERS:-true}"

"$(dirname "$0")/migrate.sh"
"$(dirname "$0")/smoke_test.sh"
terraform -chdir="${TF_DIR}" output
