# ArmorIQ integration

ArmorIQ is the machine approval layer for autonomous execution. The operator approves the mission envelope; ArmorIQ decides each proposed action inside it.

## SDK local-tool enforcement

Live mode uses the official `armoriq-sdk` session API rather than calling ArmorIQ HTTP endpoints directly. The application starts a one-tool plan, receives a short-lived intent token, calls `session.check()` in SDK mode, and executes its existing local adapter only after an explicit allow. After execution it calls `session.report()` so the result is recorded in ArmorIQ. A network failure, malformed token, ambiguous response, block, or missing configuration denies the action.

The local autonomy policy remains a mandatory precondition. ArmorIQ cannot widen the application policy: local `DENY`, `REPLAN`, or `ESCALATE` results stop before token issuance. An ArmorIQ allow is then bound to the exact local tool arguments by the SDK plan and by the application's signed permit.

Required live settings are `ARMORIQ_MODE=remote`, `ARMORIQ_API_KEY`, `ARMORIQ_USER_ID`, and `ARMORIQ_AGENT_ID`. `ARMORIQ_OPERATOR_EMAIL` is optional for service-account jobs and should be set when policy and audit records must be scoped to an operator. `ARMORIQ_BASE_URL` is an optional SDK backend override; production currently uses `https://api.armoriq.ai`.

Before a live run, create or assign an ArmorIQ policy for agent ID `armoriq-partner-agent` that governs the local tool names below. ArmorIQ organizations default to blocking tools with no matching policy, so a missing assignment returns `no_matching_policy` even when token issuance and API-key authentication succeed.

`discover`, `web_research`, `evidence_validator`, `scoring_model`, `contact_search`, `strategy_model`, `writing_model`, `gmail_send`, `gmail_reply_sync`, `qualification_model`, `calendar_freebusy`, `calendar_create`, and `docs_create`.

The versioned [`armoriq.yaml`](../armoriq.yaml) registers agent `armoriq-partner-agent`, explicitly allows every intended local tool except email delivery, and gives `partner-agent-local.gmail_send` an explicit deny. Explicit entries are used because the current SDK enforcement endpoint does not expand a namespace wildcard into its resolved allow-list. Deny precedence is enforced by ArmorIQ; the application does not contain a special-case email denial. Register changes with `armoriq register --config armoriq.yaml`. The application's mission-safety prerequisites still apply uniformly to every action before ArmorIQ enforcement.

The `mcp` Compose service exposes the current local adapter at `/mcp` using ArmorIQ's required JSON-RPC-over-HTTP/SSE contract. It implements `initialize`, `tools/list`, and `tools/call`, requires `X-API-Key`, and advertises only the fixed tool inventory used by the specialists. The adapter is still deterministic; replacing it with real Workspace implementations does not change the MCP contract.

For the current SDK enforce-only pattern, the CLI discovers the local endpoint and sends its inventory during registration; ArmorIQ then evaluates policy while execution remains in the application's local adapter. A public HTTPS URL is still required before switching to ArmorIQ proxy `invoke()`, because the proxy must reach `tools/call`. Set a strong `MCP_SERVER_API_KEY`, deploy the MCP service, update the URL in `armoriq.yaml`, then rerun `armoriq validate --config armoriq.yaml` and `armoriq register --config armoriq.yaml`.

## Authorization contract

A request contains tenant, mission, agent identity, captured purpose, committed plan version, tool and operation, resource/recipient, canonical input hash, evidence IDs and hashes, risk signals, budget counters, idempotency key, and requested expiry. A permit is signed, short-lived, single-purpose, and bound to all material inputs.

The gateway rejects missing, expired, replayed, mismatched, widened, or unverifiable permits. Recipient, body, attendees, permissions, evidence, or operation changes require reauthorization. Decisions are `PERMIT`, `DENY`, `REPLAN`, or `ESCALATE`; only `PERMIT` can execute.

Production must never use mock mode or fall back when ArmorIQ is unavailable. Availability failures are authorization failures. Store token and plan identifiers plus redacted policy metadata, not API keys, raw intent tokens, or message secrets. Verify actual effects against the permit after execution.

Suggested policy families cover mission scope, verified evidence, sourced contact, suppression, per-domain and daily limits, approved tools/scopes, message claim coverage, reply-stop behavior, scheduling consent, attendee boundaries, Drive sharing, spend, and anomaly escalation.
