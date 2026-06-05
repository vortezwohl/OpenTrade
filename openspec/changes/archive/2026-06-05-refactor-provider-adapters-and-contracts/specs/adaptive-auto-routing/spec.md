## ADDED Requirements

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