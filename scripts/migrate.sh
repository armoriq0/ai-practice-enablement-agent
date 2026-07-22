#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-east1}"
APP_NAME="${APP_NAME:-armoriq-partner}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
SERVICE="${APP_NAME}-${ENVIRONMENT}-backend"
IMAGE="$(gcloud run services describe "${SERVICE}" --region "${GCP_REGION}" --format='value(spec.template.spec.containers[0].image)')"
JOB="${APP_NAME}-${ENVIRONMENT}-migrate"

gcloud run jobs describe "${JOB}" --region "${GCP_REGION}" >/dev/null 2>&1 && action=update || action=create
gcloud run jobs "${action}" "${JOB}" --region "${GCP_REGION}" --image "${IMAGE}" \
  --service-account "${APP_NAME}-${ENVIRONMENT}-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances "${GCP_PROJECT_ID}:${GCP_REGION}:${APP_NAME}-${ENVIRONMENT}-postgres" \
  --set-secrets DATABASE_URL=database-url:latest --command alembic --args upgrade,head
gcloud run jobs execute "${JOB}" --region "${GCP_REGION}" --wait

