# Google Workspace setup

1. In the same GCP project, enable Gmail, Calendar, Drive, and Docs APIs (`scripts/configure_google_oauth.sh`).
2. Configure the OAuth consent screen. Use an Internal app for a single Workspace organization; otherwise complete External-app verification where required.
3. Create an OAuth 2.0 Web application client. Add the exact Terraform `oauth_redirect_uri` output and the local callback from `.env.example`.
4. Request only the scopes the implemented adapters require. Prefer Gmail compose/modify over full mailbox access, Calendar events/free-busy, Drive file, and Documents scopes. Explain every sensitive scope on the consent screen.
5. Store the client ID and secret with `scripts/configure_secrets.sh`. Never place them in frontend environment variables.
6. Connect each operating user in the application. Tokens must be encrypted at rest, refreshed server-side, and revocable.

A service account cannot access a user's Gmail by default. Domain-wide delegation is optional, requires an explicit Workspace super-administrator grant for exact scopes, and should not be enabled merely to avoid user OAuth. Configure test users while the consent screen is in testing status.

