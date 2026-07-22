#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${CONFIRM_TEARDOWN:?Set CONFIRM_TEARDOWN to the exact project ID}"
[[ "${CONFIRM_TEARDOWN}" == "${GCP_PROJECT_ID}" ]] || { echo "Confirmation mismatch" >&2; exit 1; }
ENVIRONMENT="${ENVIRONMENT:-dev}"
[[ "${ENVIRONMENT}" != "prod" || "${ALLOW_PRODUCTION_TEARDOWN:-false}" == "true" ]] || {
  echo "Production teardown requires ALLOW_PRODUCTION_TEARDOWN=true" >&2; exit 1;
}
terraform -chdir="infra/terraform/environments/${ENVIRONMENT}" destroy

