## ADDED Requirements

### Requirement: Provider invocation SHALL use explicit request adaptation for shared command families
The system SHALL translate normalized shared request fields into provider-specific invocation arguments using explicit adaptation logic for shared command families such as history, realtime, profile, search, and resolve. Shared provider execution SHALL NOT rely on generic passthrough as the primary behavior for those command families.

#### Scenario: History request is translated into provider-specific history kwargs
- **WHEN** a normalized shared history request is dispatched to a concrete provider
- **THEN** the provider adaptation layer SHALL build provider-specific invocation arguments from normalized shared fields before calling the upstream provider API

#### Scenario: Resolve request adapts shared quote lookup semantics explicitly
- **WHEN** a normalized resolve quote-id request is dispatched to a concrete provider
- **THEN** the provider adaptation layer SHALL map shared lookup semantics to provider-specific input without requiring raw shared callers to know provider-native parameter names

### Requirement: Shared market semantics SHALL be adapted separately from provider-native filters
The system SHALL treat shared market semantics and provider-native filter expressions as separate concerns. Shared multi-backend commands SHALL use semantic market input, while provider-native filter expressions SHALL only be introduced inside provider-specific adaptation paths or provider-specific extensions.

#### Scenario: Shared stock live request uses semantic market input
- **WHEN** a shared stock live request is executed with a semantic market value such as `A_stock`
- **THEN** the provider adaptation layer SHALL translate that semantic market into provider-native input rather than passing the shared market value through as a provider-native filter expression

#### Scenario: Provider-specific filter command keeps explicit provider adaptation path
- **WHEN** a command requires a provider-native filter syntax that is not meaningfully shareable across backends
- **THEN** the system SHALL keep that syntax isolated to a provider-specific adaptation path or extension command instead of reusing shared market semantics directly

### Requirement: Shared stock profile SHALL use single-instrument semantics
The system SHALL treat shared `stock.profile` as a single-instrument capability. Shared execution and provider adaptation SHALL reject ambiguous multi-instrument profile requests rather than silently delegating them to provider-specific multi-instrument behavior.

#### Scenario: Stock profile rejects multi-instrument request at shared boundary
- **WHEN** a shared stock profile request contains more than one target instrument
- **THEN** the system SHALL fail with a readable request error that indicates the shared capability is single-instrument

#### Scenario: Stock profile provider adaptation receives one normalized target
- **WHEN** a valid shared stock profile request is dispatched to a provider
- **THEN** the provider adaptation layer SHALL receive exactly one normalized target instrument for that request
