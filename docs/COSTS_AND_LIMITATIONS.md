# Costs, limitations, and backlog

## Cost drivers

Cloud Run scales with requests; Cloud SQL is the main fixed baseline; model research/generation and third-party search vary with mission volume. Cloud Tasks, Scheduler, logs, monitoring, Secret Manager, and Artifact Registry are generally smaller contributors. Obtain current pricing with the Google and OpenAI calculators before launch and set project budgets and model-level mission budgets.

A small development deployment typically uses scale-to-zero services and a small database. Production should use regional Cloud SQL, minimum backend capacity, log retention controls, and explicit alert notification channels. Exact totals depend on traffic, token use, retention, and provider contracts.

## Known limitations

- Google OAuth consent and domain policies require administrator action and cannot be fully automated.
- ArmorIQ availability is on the critical path by design; outages deny external effects.
- Public evidence can be stale or misleading even when provenance is valid.
- Contacts must be publicly sourced or explicitly provided; the system does not infer addresses.
- Scheduling supports bounded slot negotiation, not arbitrary contractual commitments.
- Cloud Monitoring notification recipients and custom domains are organization-specific inputs.
- A production deployment requires real credentials and billing-enabled cloud resources.

## Backlog

Add private-IP-only Cloud SQL with organization-specific networking, external immutable audit export, richer queue/SLO dashboards, automated OAuth scope verification, policy simulation and canary missions, regional disaster recovery, advanced relationship-graph providers, and continuous adversarial evidence tests.

