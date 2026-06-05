# shared-provider-contracts Specification

## Purpose
TBD - created by archiving change refactor-provider-adapters-and-contracts. Update Purpose after archive.
## Requirements
### Requirement: Shared commands SHALL expose provider-neutral request semantics
For every multi-backend shared command, the internal request schema SHALL use provider-neutral field semantics instead of backend-native parameter spelling. Backend-native request parameters SHALL only exist inside provider adapter modules.

#### Scenario: Shared history command does not depend on backend-native field names
- **WHEN** a multi-backend history command is defined in the shared command catalog
- **THEN** its stable request fields MUST use provider-neutral semantics such as symbol, date, timeframe, adjustment, market, or quote identifiers
- **THEN** backend-native names such as `fs`, `beg`, `end`, `klt`, or `fqt` MUST NOT be the defining shared contract for that command

#### Scenario: Provider adapter performs backend-native translation
- **WHEN** a provider requires backend-native kwargs that differ from the shared schema
- **THEN** the selected provider adapter SHALL translate the provider-neutral request into backend-native kwargs before invoking the third-party callback
- **THEN** the CLI, facade, and shared catalog MUST NOT rely on the caller to know that backend-native spelling

### Requirement: Shared command support matrices SHALL reflect real backend capability
A shared command SHALL only declare backend support, market support, and request cardinality that the current provider adapter can truthfully satisfy.

#### Scenario: Shared schema does not overstate multi-value support
- **WHEN** a shared command is declared with multi-value input such as multiple symbols or quote identifiers
- **THEN** every backend listed in its support matrix MUST either support that multi-value shape or explicitly translate it to a compatible backend-native execution path
- **THEN** the system MUST NOT keep a backend in the shared support matrix if that backend only fails later because the declared cardinality was untrue

#### Scenario: Shared schema does not overstate market support
- **WHEN** a shared command accepts a market enum in its provider-neutral schema
- **THEN** each backend listed for that command MUST have an adapter path for that market semantic or reject the backend at capability-definition time
- **THEN** the system MUST NOT present unsupported market/backend combinations as if they were valid shared behavior

### Requirement: Contract tightening SHALL fail early and explicitly
When a shared command cannot truthfully support a backend, identifier shape, or market semantic, the system SHALL fail at the shared contract or provider adapter boundary with an explicit contract error instead of silently depending on undefined provider behavior.

#### Scenario: Unsupported backend path is rejected before raw provider drift
- **WHEN** a shared command receives an input shape that the selected backend cannot truthfully adapt
- **THEN** the system SHALL raise an explicit provider contract error at the adaptation boundary
- **THEN** the failure MUST identify the backend and command instead of surfacing only a late third-party exception

