# provider-request-adaptation Specification

## Purpose
TBD - created by archiving change fix-shared-command-routing-and-adaptation. Update Purpose after archive.
## Requirements
### Requirement: Provider invocation SHALL use explicit request adaptation for shared command families
The system SHALL translate normalized shared request fields into provider-specific invocation arguments using explicit adaptation logic for shared command families such as history, realtime, profile, search, and resolve. Shared provider execution SHALL NOT rely on generic passthrough as the primary behavior for those command families. Shared `quote.*` execution SHALL explicitly translate provider-neutral identifiers into backend-native identifiers whenever a backend requires a native identifier contract.

#### Scenario: History request is translated into provider-specific history kwargs
- **WHEN** a normalized shared history request is dispatched to a concrete provider
- **THEN** the provider adaptation layer SHALL build provider-specific invocation arguments from normalized shared fields before calling the upstream provider API

#### Scenario: Resolve request adapts shared quote lookup semantics explicitly
- **WHEN** a normalized resolve quote-id request is dispatched to a concrete provider
- **THEN** the provider adaptation layer SHALL map shared lookup semantics to provider-specific input without requiring raw shared callers to know provider-native parameter names

#### Scenario: Efinance quote latest does not passthrough shared symbols as native quote identifiers
- **WHEN** a normalized shared `quote.price.latest` request is dispatched to the `efinance` backend
- **THEN** the provider adaptation layer SHALL translate the shared identifiers into Eastmoney `quote_id` input before invoking `efinance.common.get_latest_quote`
- **THEN** the provider execution path SHALL NOT depend on generic passthrough of `symbols` or legacy `quote_ids` fields as if they were already backend-native identifiers

#### Scenario: Efinance quote profile does not passthrough shared symbol as native quote identifier
- **WHEN** a normalized shared `quote.profile` request is dispatched to the `efinance` backend
- **THEN** the provider adaptation layer SHALL translate the shared identifier into a concrete Eastmoney `quote_id` before invoking the upstream base-info callback
- **THEN** the command SHALL NOT require the shared caller to know or pass the backend-native identifier form

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

### Requirement: Shared requests SHALL be translated through explicit provider adapters
Every multi-backend shared command SHALL reach third-party callbacks through an explicit provider adaptation boundary. The adapter SHALL be responsible for translating provider-neutral request semantics into backend-native request kwargs.

#### Scenario: Shared request translation occurs before provider invocation
- **WHEN** a shared command is executed against a concrete backend
- **THEN** the selected provider adapter SHALL derive backend-native kwargs from the provider-neutral request contract before invoking the third-party callback
- **THEN** upper execution layers MUST NOT invoke third-party callbacks by directly passing the provider-neutral shared request as raw kwargs

### Requirement: Provider adaptation SHALL be modularized by backend
Explicit provider request adaptation logic SHALL live in the backend-specific provider modules rather than in a single cross-backend implementation file.

#### Scenario: Backend-specific adaptation remains local to the backend module
- **WHEN** a provider-specific request translation such as efinance market mapping, akshare catalog interpretation, or yfinance ticker conversion is implemented
- **THEN** that adaptation logic SHALL be defined in the matching backend module inside `opentrade/backends`
- **THEN** unrelated backend modules and common helper modules MUST NOT own that provider-specific translation rule

