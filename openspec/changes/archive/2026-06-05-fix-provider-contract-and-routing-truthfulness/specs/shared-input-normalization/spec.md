## MODIFIED Requirements

### Requirement: Shared commands SHALL accept provider-neutral normalized input
The system SHALL define provider-neutral internal request fields for multi-backend shared commands instead of exposing provider-native parameter names as the primary internal contract. Shared command execution SHALL normalize dates, symbol identifiers, quote identifiers, market semantics, timeframe, and adjustment into stable internal field names before provider selection and provider invocation. The normalized contract SHALL be the single source of truth consumed consistently by planners, facades, and provider adapters.

#### Scenario: History command normalizes dates and timeframe before provider invocation
- **WHEN** a shared history command is invoked with CLI inputs for symbols, start date, end date, timeframe, and adjustment
- **THEN** the system SHALL produce a normalized request object that uses provider-neutral field names rather than provider-native names such as `beg`, `end`, `klt`, or `fqt`

#### Scenario: Shared normalization accepts compact date input
- **WHEN** a user provides a date input in compact `YYYYMMDD` form for a shared command
- **THEN** the normalized request SHALL preserve that semantic date value and defer provider-specific formatting to the provider adaptation layer

#### Scenario: Quote latest normalizes to shared symbols rather than provider-native quote identifier fields
- **WHEN** a shared `quote.price.latest` command is invoked through CLI or internal execution
- **THEN** the normalized request SHALL expose provider-neutral shared identifier fields such as `symbols`
- **THEN** downstream planner and adapter code SHALL consume that normalized field instead of relying on provider-native legacy names such as `quote_ids` or `quote_id_list`

#### Scenario: Quote profile normalizes to shared symbol rather than provider-native quote identifier field
- **WHEN** a shared `quote.profile` command is invoked through CLI or internal execution
- **THEN** the normalized request SHALL expose a provider-neutral shared identifier field such as `symbol`
- **THEN** downstream planner and adapter code SHALL treat provider-native identifier translation as an adapter concern

### Requirement: Shared market semantics SHALL be validated by schema metadata rather than hard-coded field names
The system SHALL validate shared market semantics based on schema-declared field meaning instead of hard-coding validation only for a field literally named `market`. Any shared field that represents market semantics SHALL use the same validation and normalization path.

#### Scenario: Shared market_type field receives market validation
- **WHEN** a shared command declares a market semantic field using a name such as `market_type`
- **THEN** the request validation layer SHALL apply shared market validation to that field

#### Scenario: Unsupported shared market enum is rejected consistently
- **WHEN** a user provides an unsupported shared market enum to any shared command
- **THEN** the system SHALL fail validation with the same class of readable request error regardless of the internal field name used by that command

### Requirement: Runtime command metadata SHALL come from repository-owned sources
The system SHALL load shared command metadata and field definitions from repository-owned sources that are versioned with the project, and SHALL NOT require an external skill reference directory as the runtime truth source for command behavior.

#### Scenario: Shared command catalog is available without external skill runtime data
- **WHEN** the project command catalog is initialized in a normal repository checkout
- **THEN** the shared command definitions SHALL be constructed from repository-owned metadata rather than an external `.skill` runtime file