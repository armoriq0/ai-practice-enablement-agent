#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-east1}"
gcloud services enable gmail.googleapis.com calendar-json.googleapis.com drive.googleapis.com docs.googleapis.com
cat <<EOF
Google API services are enabled.

Complete these console-only steps:
1. Configure the OAuth consent screen and requested Gmail/Calendar/Drive/Docs scopes.
2. Create a Web application OAuth client.
3. Add the Terraform output oauth_redirect_uri as an authorized redirect URI.
4. Run scripts/configure_secrets.sh to store the client ID and client secret.

Domain-wide delegation is not enabled by this script and must never be assumed.
EOF

