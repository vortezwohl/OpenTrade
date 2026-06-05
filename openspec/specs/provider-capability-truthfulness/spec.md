# provider-capability-truthfulness Specification

## Purpose
TBD - created by archiving change refactor-provider-adapters-and-contracts. Update Purpose after archive.
## Requirements
### Requirement: Shared capability declarations SHALL match real execution truth
The command catalog, backend support matrix, and provider adapter set SHALL describe only capabilities that can be truthfully executed by the current implementation.

#### Scenario: Shared backend support excludes unimplemented adapter behavior
- **WHEN** a shared command lists a backend in its supported backend matrix
- **THEN** that backend MUST have a real adapter path for the declared request shape and result contract
- **THEN** the project MUST NOT keep a backend listed solely because it might work for some inputs while failing for the command's declared semantics

### Requirement: Cardinality truth SHALL be aligned across schema, adapter, and provider behavior
Single-value and multi-value support SHALL be consistent across the request schema, backend support declaration, and provider adapter implementation.

#### Scenario: Single-value command stays single-value end to end
- **WHEN** a shared command is defined as a single-target capability such as a single profile lookup
- **THEN** its schema, adapter, and provider execution path SHALL all enforce the same single-value assumption
- **THEN** the system MUST NOT advertise multi-value support in one layer while depending on single-value assumptions in another layer

#### Scenario: Multi-value command remains truthful for all listed backends
- **WHEN** a shared command is defined as accepting multiple identifiers
- **THEN** every listed backend MUST support that multi-value contract directly or via explicit adapter orchestration
- **THEN** the system MUST NOT rely on hidden backend-specific behavior that only succeeds for one-item input while the schema promises more

### Requirement: Contract truth SHALL drive auto-routing inputs
Auto backend planning SHALL consume only truthful shared capability data. Candidate ordering MUST NOT depend on capability assumptions that the command catalog or adapters cannot actually honor.

#### Scenario: Auto planning uses truthful capability boundaries
- **WHEN** auto backend planning chooses a candidate chain for a shared command
- **THEN** it SHALL only consider backends whose declared support is truthful for that command's identifier shape, market semantic, and cardinality
- **THEN** auto routing MUST NOT prefer or retain a backend that is known to be incompatible with the normalized shared request

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

