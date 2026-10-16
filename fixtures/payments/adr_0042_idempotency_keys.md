# ADR-0042: Mandating 48-Hour Idempotency Keys on Payment Settlement

> **Notice:** SYNTHETIC FIXTURE - FOR COMPANY BRAIN BENCHMARK & DEMO ONLY.

- **Document ID:** `doc_adr_0042`
- **Source URI:** `doc://company-wiki/architecture/adr-0042-payment-idempotency.md`
- **Decision ID:** `dec_adr_0042`
- **Status:** `ACCEPTED`
- **Decided At:** `2026-09-15T16:30:00Z`
- **Decided By:** `emp_engineer` (Asha Patel), `emp_eng_manager` (Marcus Chen)
- **Affects:** `proj_payments_v2`, `svc_payments_settlement`

## Context

During Q3 load spikes, network retries from checkout clients resulted in concurrent requests reaching payment worker nodes before the primary database write completed. This resulted in duplicate transaction records and multiple authorizations against card networks.

## Decision Rationale

We mandate an explicit 48-hour idempotency key strategy across all write operations on `svc_payments_settlement`:
1. Every client mutation request must include an `Idempotency-Key` header with a unique UUID v4.
2. In-flight requests obtain a short-lived distributed mutex lock with a 5-second TTL.
3. Completed transaction payloads are cached with an expiration of 48 hours to reliably return idempotent replies.

## Consequences & Unresolved Considerations

- **Positive:** Eliminates double-charging caused by client-side retries.
- **Unresolved Risk:** External banking webhooks delivered asynchronously do not always transmit the client-originated header. As noted in issue PAY-104, webhook retries from banking gateways require a secondary deduplication barrier based on transaction reference hashes.
