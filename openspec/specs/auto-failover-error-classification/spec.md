# auto-failover-error-classification Specification

## Purpose
TBD - created by archiving change fix-real-api-provider-guardrails. Update Purpose after archive.
## Requirements
### Requirement: Auto backend shall make failover decisions from classified provider errors
The system SHALL decide whether `auto` continues to the next backend from classified error semantics instead of raw Python exception types alone. Local request contract errors MUST stop failover immediately. Provider execution failures, provider response-shape failures, network failures, and rate-limit failures MUST remain eligible for failover when another candidate backend is available.

#### Scenario: Recoverable provider failure triggers next backend
- **WHEN** the first backend in an `auto` candidate chain fails with a classified provider execution failure such as rate limit, remote disconnect, or upstream response-shape error
- **THEN** the system SHALL record the failed attempt
- **THEN** the system SHALL continue to the next eligible backend candidate instead of terminating on the original raw exception type

#### Scenario: Local contract error stops auto immediately
- **WHEN** the current backend rejects the normalized request because the request contract cannot be satisfied locally, such as unsupported market semantics or an invalid single-vs-multi target shape
- **THEN** the system SHALL stop failover immediately
- **THEN** the user SHALL receive a local contract error rather than an aggregated provider-failure chain

#### Scenario: All candidates fail with classified provider failures
- **WHEN** every backend candidate in an `auto` chain fails with a classified provider failure
- **THEN** the final error SHALL aggregate the attempted backends and their failure summaries
- **THEN** the final error MUST preserve enough information for reports and traces to distinguish provider failure from local contract rejection

