#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-east1}"
ARTIFACT_REPOSITORY="${ARTIFACT_REPOSITORY:-armoriq-partner}"
TF_STATE_BUCKET="${TF_STATE_BUCKET:-${GCP_PROJECT_ID}-armoriq-partner-tfstate}"

command -v gcloud >/dev/null || { echo "gcloud is required" >&2; exit 1; }
gcloud auth print-access-token >/dev/null
gcloud config set project "${GCP_PROJECT_ID}"
gcloud services enable \
  artifactregistry.googleapis.com cloudbuild.googleapis.com run.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com cloudtasks.googleapis.com \
  cloudscheduler.googleapis.com monitoring.googleapis.com logging.googleapis.com \
  iamcredentials.googleapis.com

if ! gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY}" --location "${GCP_REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${ARTIFACT_REPOSITORY}" --location "${GCP_REGION}" \
    --repository-format docker --description "ArmorIQ partner agent images"
fi

if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" --location "${GCP_REGION}" \
    --uniform-bucket-level-access
  gcloud storage buckets update "gs://${TF_STATE_BUCKET}" --versioning
fi

echo "Bootstrap complete. Terraform state bucket: ${TF_STATE_BUCKET}"

