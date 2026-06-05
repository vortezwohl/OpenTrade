## ADDED Requirements

### Requirement: Shared capability declarations SHALL match real provider support
The system SHALL declare shared backend support only for request shapes and market semantics that the selected provider can consume truthfully through its adapter.

#### Scenario: Single-target-only backend path is not advertised as batch-safe
- **WHEN** a shared command is implemented by a backend path that only supports one target instrument at a time
- **THEN** the system SHALL constrain that backend path through schema, adapter truthfulness rules, or candidate filtering
- **THEN** the shared capability matrix SHALL NOT imply unrestricted multi-target support for that backend

#### Scenario: Unsupported market semantics are excluded from truthful support
- **WHEN** a backend cannot truthfully consume a shared market semantic for a command family
- **THEN** the system SHALL treat that backend-command-market combination as unsupported at contract level
- **THEN** auto routing SHALL NOT continue to advertise that backend as a normal candidate for that request

### Requirement: Truthfulness constraints SHALL fail early and readably
The system SHALL expose truthful-support violations as stable local contract failures instead of relying on remote API failures to reveal unsupported combinations.

#### Scenario: Unsupported backend-target shape fails before upstream invocation
- **WHEN** a shared request shape cannot be truthfully adapted for the selected backend
- **THEN** the system SHALL fail before the upstream third-party callback is invoked
- **THEN** the error SHALL identify the backend and command as a local contract mismatch rather than a remote provider crash