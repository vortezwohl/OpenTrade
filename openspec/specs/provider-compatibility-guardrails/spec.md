# provider-compatibility-guardrails Specification

## Purpose
TBD - created by archiving change fix-real-api-provider-guardrails. Update Purpose after archive.
## Requirements
### Requirement: Shared date inputs shall be normalized before provider invocation
For shared commands that expose provider-neutral date inputs, the adapter layer SHALL normalize supported date formats to the concrete provider format required by the selected backend. This normalization MUST happen before the third-party callback is invoked.

#### Scenario: Leaderboard query accepts shared compact date input
- **WHEN** `stock leaderboard daily` is executed with `--start-date 20250530 --end-date 20250530` against a backend whose upstream API requires `%Y-%m-%d`
- **THEN** the adapter SHALL convert the compact shared date input to the provider-required date format before invoking the third-party callback
- **THEN** the command MUST NOT fail only because the shared input used `YYYYMMDD`

#### Scenario: Holder count query accepts shared compact date input
- **WHEN** `stock holders latest-count` is executed with a compact shared `--date` value against a backend whose upstream API requires `%Y-%m-%d`
- **THEN** the adapter SHALL normalize that date before invoking the third-party callback
- **THEN** the user MUST NOT be required to know the backend-specific date separator convention

### Requirement: Known upstream malformed responses shall be classified as provider failures
When a third-party provider crashes because of malformed upstream payloads or internal parsing failures, the local system SHALL classify the failure as a provider-side failure instead of a user input error. The system MUST NOT fabricate a success result from such failures.

#### Scenario: Explicit backend surfaces stable provider failure
- **WHEN** an explicitly selected backend encounters a known upstream malformed-response path such as `fund profile` crashing inside efinance or `bond flow today` failing on a boolean payload
- **THEN** the system SHALL surface a stable provider failure classification that identifies the command and backend
- **THEN** the system MUST NOT return an empty success payload or misreport the failure as a local CLI argument error

#### Scenario: Auto mode can continue after known upstream malformed response
- **WHEN** a backend in `auto` mode fails because of a classified upstream malformed-response path
- **THEN** the failure SHALL remain eligible for failover according to the auto failover policy
- **THEN** subsequent backend attempts SHALL still be recorded in trace or reporting metadata

