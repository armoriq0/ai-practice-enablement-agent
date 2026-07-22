#!/usr/bin/env bash
set -euo pipefail
BACKEND_URL="${BACKEND_URL:-}"
FRONTEND_URL="${FRONTEND_URL:-}"
if [[ -z "${BACKEND_URL}" && -n "${GCP_PROJECT_ID:-}" ]]; then
  BACKEND_URL="$(gcloud run services describe "${APP_NAME:-armoriq-partner}-${ENVIRONMENT:-prod}-backend" --region "${GCP_REGION:-us-east1}" --format='value(status.url)')"
fi
if [[ -z "${FRONTEND_URL}" && -n "${GCP_PROJECT_ID:-}" ]]; then
  FRONTEND_URL="$(gcloud run services describe "${APP_NAME:-armoriq-partner}-${ENVIRONMENT:-prod}-frontend" --region "${GCP_REGION:-us-east1}" --format='value(status.url)')"
fi
: "${BACKEND_URL:?Set BACKEND_URL or GCP_PROJECT_ID}"
: "${FRONTEND_URL:?Set FRONTEND_URL or GCP_PROJECT_ID}"
authorization=""
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
  identity_token="$(gcloud auth print-identity-token)"
  authorization="Authorization: Bearer ${identity_token}"
fi
probe() {
  if [[ -n "${authorization}" ]]; then
    curl -H "${authorization}" --fail --silent --show-error --retry 8 "$1" >/dev/null
  else
    curl --fail --silent --show-error --retry 8 "$1" >/dev/null
  fi
}
probe "${BACKEND_URL}/api/v1/health"
probe "${BACKEND_URL}/api/v1/readiness"
probe "${FRONTEND_URL}"
echo "Smoke tests passed: ${BACKEND_URL} ${FRONTEND_URL}"
