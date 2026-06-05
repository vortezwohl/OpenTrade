# adaptive-auto-routing Specification

## Purpose
TBD - created by archiving change fix-shared-command-routing-and-adaptation. Update Purpose after archive.
## Requirements
### Requirement: Auto backend planning SHALL use normalized request semantics
The system SHALL derive auto backend candidate order after shared request normalization, using command capability, market semantics, and identifier shape rather than a single static global candidate order for all shared commands. Candidate planning SHALL also remove backend candidates that are known not to support the current normalized request truthfully.

#### Scenario: A-share shared request prefers the strongest local market backend first
- **WHEN** a shared command targets A-share semantics or a local quote identifier shape that maps to domestic market data
- **THEN** auto backend planning SHALL rank the strongest local market backend ahead of less suitable candidates

#### Scenario: US ticker shared request prefers the Yahoo-oriented backend first
- **WHEN** a shared command targets a US ticker or explicit US market semantics
- **THEN** auto backend planning SHALL rank the Yahoo-oriented backend ahead of domestic-market-first backends

#### Scenario: Truthfulness filter removes known-incompatible backend candidate
- **WHEN** a normalized shared request is known to be unsupported by a backend because of target cardinality, identifier shape, or market semantics
- **THEN** auto backend planning SHALL remove that backend from the candidate chain before execution begins
- **THEN** the candidate chain SHALL represent only truthfully executable backend options for that request

### Requirement: Auto planning SHALL remain request-aware across watch iterations
The system SHALL preserve request-aware auto planning for every execution cycle, including watch mode, instead of falling back to a static precomputed candidate chain that ignores normalized request semantics.

#### Scenario: Watch mode rebuilds or reuses the same request-aware candidate semantics
- **WHEN** a shared auto-routed command runs in watch mode for multiple iterations
- **THEN** each iteration SHALL use the same request-aware backend planning semantics as a normal single execution

### Requirement: Auto execution SHALL expose candidate planning and final resolution metadata
The system SHALL expose enough metadata for raw output and regression reports to distinguish requested backend, planned candidate order, attempted candidates, final backend, and whether the final result required fallback.

#### Scenario: Raw output records final backend after fallback
- **WHEN** an auto-routed shared command succeeds on a non-first candidate
- **THEN** raw metadata SHALL identify the planned candidate order and the final backend that produced the successful result

#### Scenario: Raw output records unresolved auto chain when no candidate succeeds
- **WHEN** an auto-routed shared command fails before any candidate completes successfully
- **THEN** raw metadata and regression output SHALL record that no final backend was reached

#### Scenario: Quote shared command planning reads normalized shared field names
- **WHEN** a normalized shared `quote.price.latest` or `quote.profile` request is planned in auto mode
- **THEN** the planner SHALL derive identifier shape from the normalized shared `symbols` or `symbol` fields
- **THEN** the planner SHALL NOT depend on obsolete pre-normalization field names such as `quote_ids` or `quote_id` to detect candidate suitability

### Requirement: Auto routing SHALL depend on truthful normalized shared semantics
Auto backend candidate planning SHALL be based on normalized shared request semantics that have already been validated against truthful capability and identifier contracts.

#### Scenario: Auto routing excludes backends that are incompatible with the normalized contract
- **WHEN** a shared command is executed in auto mode after request normalization
- **THEN** auto routing SHALL only include backend candidates whose identifier semantics, market support, and cardinality support are truthful for that request
- **THEN** the candidate chain MUST NOT be built from assumptions that were only valid under the old ambiguous shared contract

### Requirement: Auto routing SHALL remain decoupled from provider file layout
Refactoring provider implementations into multiple backend modules SHALL NOT change the external auto-routing contract or require planner callers to know where backend code lives.

#### Scenario: Auto planner continues to work through the factory boundary
- **WHEN** the backend provider code is modularized under the `backends` package
- **THEN** auto routing SHALL continue to operate through backend names, provider lookup, and truthful capability metadata
- **THEN** planner logic MUST NOT become coupled to specific backend implementation module paths

