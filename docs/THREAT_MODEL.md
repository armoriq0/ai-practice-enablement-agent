# Threat model

## Protected assets

OAuth tokens, customer and contact data, evidence provenance, mission delegations, ArmorIQ permits, outbound messages, calendars, Drive permissions, audit records, credentials, and budget/contact limits.

## Principal threats and controls

| Threat | Primary controls |
|---|---|
| Prompt injection in public research | Treat sources as data; extract facts through schemas; strip active content; never expose tools to research text; injection detector and evidence quarantine |
| Model fabricates a claim or contact | Source-level provenance, independent evidence verification, claim-to-source coverage, no guessed addresses, policy denial |
| Agent exceeds delegated purpose | Versioned mission envelope, committed plan, least-privilege tool identity, ArmorIQ action-bound permit |
| Permit replay or confused deputy | Short TTL, canonical input hash, audience/tool/target binding, nonce and idempotency ledger, immediate validation |
| Scheduler or task bypass | OIDC caller validation; scheduler only creates workflow intent; gateway independently authorizes effects |
| Unauthorized email/calendar/share | Suppression and consent checks, exact recipient/attendee/permission binding, governed gateway, effect verification |
| Credential or token disclosure | Secret Manager, encrypted OAuth tokens, log redaction, no client-side secrets, scoped access and rotation |
| Cross-tenant access | Tenant filters in every query, RBAC, object-level authorization, tenant-bound tasks and permits |
| Audit tampering | Append-only records, hash chaining, external log export, decision ID correlation, continuous verifier |
| Resource or cost exhaustion | Queue rates, concurrency caps, contact and spend budgets, deadlines, retries with dead-letter persistence, circuit breakers |
| SSRF through evidence fetch | HTTPS allow policy, DNS/IP validation before connection, redirect revalidation, size/time/content limits |

Residual risks include provider compromise, OAuth user compromise, sophisticated source poisoning, mistaken but internally consistent evidence, and policy misconfiguration. Mitigate through revocation, anomaly alerts, conservative limits, independent sources, and periodic red-team evaluations.

