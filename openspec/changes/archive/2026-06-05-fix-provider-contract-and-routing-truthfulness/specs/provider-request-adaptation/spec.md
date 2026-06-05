## MODIFIED Requirements

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