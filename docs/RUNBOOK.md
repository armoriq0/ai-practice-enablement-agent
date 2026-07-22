# Operations runbook

## First response

For suspected authorization, tenant-isolation, or external-action integrity failures: set `AUTONOMOUS_EXECUTION_ENABLED=false`, pause all Scheduler jobs, stop Cloud Tasks dispatch, revoke affected OAuth grants and ArmorIQ credentials, preserve logs/audit exports, and notify the incident owner. Do not delete tasks or audit records.

## Common incidents

- **ArmorIQ unavailable:** expected behavior is fail closed. Confirm no external calls occurred, inspect decision errors, and resume only after permit validation succeeds.
- **Repeated task failures:** pause the affected queue, inspect the persisted failed-task record and trace ID, fix the cause, then replay with the original idempotency key.
- **Unexpected outbound action:** disable autonomy, revoke Workspace tokens, compare payload/result hashes with the permit, verify audit chain, and check for replay or policy drift.
- **Database pressure:** reduce queue dispatch and Cloud Run concurrency, inspect Query Insights, scale the instance, and restore normal rates gradually.
- **OAuth revoked:** mark the connection unhealthy, suppress Workspace actions, reconnect the affected user, and never silently switch identities.
- **Cost anomaly:** pause generation queues, inspect model-usage records and mission budgets, then lower concurrency or model limits.

## Recovery and rollback

Redeploy the last immutable image tag. Run backward-compatible database migrations before traffic changes; use point-in-time recovery for corruption. Keep schedulers paused during recovery. Afterward run health/readiness, policy validation, a denied-action test, a permitted sandbox action, audit verification, and smoke tests.

