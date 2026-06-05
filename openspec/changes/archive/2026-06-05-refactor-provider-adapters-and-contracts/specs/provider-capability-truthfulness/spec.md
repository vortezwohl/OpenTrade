## ADDED Requirements

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