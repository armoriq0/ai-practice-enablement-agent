#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-east1}"
APP_NAME="${APP_NAME:-armoriq-partner}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
INSTANCE_CONNECTION="${GCP_PROJECT_ID}:${GCP_REGION}:${APP_NAME}-${ENVIRONMENT}-postgres"

put_secret() {
  local env_name="$1" secret_id value
  secret_id="$(printf '%s' "${env_name}" | tr '[:upper:]_' '[:lower:]-')"
  value="${!env_name:-}"
  if [[ -z "${value}" ]]; then
    read -r -s -p "${env_name}: " value
    echo
  fi
  [[ -n "${value}" ]] || { echo "${env_name} cannot be empty" >&2; exit 1; }
  gcloud secrets describe "${secret_id}" --project "${GCP_PROJECT_ID}" >/dev/null 2>&1 || \
    gcloud secrets create "${secret_id}" --replication-policy automatic --project "${GCP_PROJECT_ID}"
  printf '%s' "${value}" | gcloud secrets versions add "${secret_id}" --data-file=- --project "${GCP_PROJECT_ID}" >/dev/null
}

required=(OPENAI_API_KEY ARMORIQ_API_KEY ARMORIQ_BASE_URL GOOGLE_OAUTH_CLIENT_ID \
  GOOGLE_OAUTH_CLIENT_SECRET GOOGLE_OAUTH_REDIRECT_URI APPLICATION_SECRET)
for secret in "${required[@]}"; do put_secret "${secret}"; done

DATABASE_PASSWORD="${DATABASE_PASSWORD:-}"
if [[ -z "${DATABASE_PASSWORD}" ]]; then
  read -r -s -p "DATABASE_PASSWORD (for partner SQL user): " DATABASE_PASSWORD
  echo
fi
[[ -n "${DATABASE_PASSWORD}" ]] || { echo "DATABASE_PASSWORD cannot be empty" >&2; exit 1; }
DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://partner:${DATABASE_PASSWORD}@/partner?host=/cloudsql/${INSTANCE_CONNECTION}}"
export DATABASE_URL
put_secret DATABASE_URL

OPTIONAL_SEARCH_PROVIDER_KEYS="${OPTIONAL_SEARCH_PROVIDER_KEYS:-{}}"
export OPTIONAL_SEARCH_PROVIDER_KEYS
put_secret OPTIONAL_SEARCH_PROVIDER_KEYS
echo "Secret versions configured. Values were not written to Terraform state."

