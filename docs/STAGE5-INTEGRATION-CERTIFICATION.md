# Stage 5 integration certification

This repository now certifies the executable Marketing boundary rather than only compiling source.

The canonical API prefix is `/v1/marketing`. All campaign, approval, audience, creative and Meta read-only routes are tenant-bound. Mutating create operations require `Idempotency-Key`; reuse with a different semantic request fails with HTTP 409. Campaign reads and transitions query by both aggregate ID and `X-Tenant-ID` so cross-tenant IDs are indistinguishable from missing records.

The disposable PostgreSQL gate applies Stage 4 and Stage 5 migrations, verifies required tables and uniqueness controls, rolls both migrations back, proves the tables were removed, reapplies them, and runs real idempotency and tenant-isolation tests.

Approval transitions require the private Kong-injected `X-Codestra-Verified-Scopes` contract. Upstream deployments must strip any public copy of that header and inject only scopes verified from the canonical Keycloak token. Direct public access to the service is forbidden.

Meta synchronization is read-only, requires `META_READ_SYNC_ENABLED=true`, and accepts only IDs in `META_ALLOWED_AD_ACCOUNT_IDS`. The adapter exposes no provider-write methods. A separate protected sandbox environment must supply the read-only test-account token; this source change does not connect credentials or execute a Meta request.

The following remain false in every normal CI and runtime example:

```text
LIVE_ADVERTISING_ENABLED=false
META_READ_SYNC_ENABLED=false
```
