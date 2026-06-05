# provider-identifier-semantics Specification

## Purpose
TBD - created by archiving change refactor-provider-adapters-and-contracts. Update Purpose after archive.
## Requirements
### Requirement: Shared identifier semantics SHALL be explicit per command family
Shared commands SHALL explicitly define whether their identifiers are provider-neutral business identifiers or provider-native passthrough identifiers. The system MUST NOT overload one shared field with multiple incompatible backend-native meanings without an explicit translation rule.

#### Scenario: Quote identifiers are not treated as ambiguous free-form IDs
- **WHEN** a shared `quote.*` command accepts a quote identifier field
- **THEN** the command contract SHALL explicitly define whether that field represents a true shared quote identifier or a backend-specific passthrough value
- **THEN** the system MUST NOT treat Eastmoney quote IDs and Yahoo tickers as interchangeable shared identifiers unless an explicit translation path exists

#### Scenario: Backend-specific identifier translation stays inside adapters
- **WHEN** a backend requires its own provider-native identifier shape
- **THEN** the provider adapter SHALL perform that identifier translation from the shared input contract
- **THEN** the caller MUST NOT be required to know backend-native identifier syntax for a command that claims shared semantics

### Requirement: A-share symbols SHALL be translated before Yahoo-specific execution
If a shared stock command routes to yfinance for A-share semantics, the adapter SHALL translate the provider-neutral stock symbol into the Yahoo-compatible ticker form before yfinance execution, or explicitly reject that backend path as unsupported.

#### Scenario: Yfinance does not receive raw shared A-share symbols by accident
- **WHEN** a shared A-share stock command is selected with yfinance as the backend
- **THEN** the yfinance adapter SHALL either translate the stock symbol into a Yahoo-compatible ticker or fail with an explicit contract error before execution
- **THEN** the system MUST NOT silently depend on the user already knowing Yahoo-specific `.SS` or `.SZ` ticker forms for a command advertised as shared

### Requirement: Identifier failures SHALL be classified as contract mismatches when translation is undefined
When no truthful translation exists from the shared identifier contract to the selected backend-native identifier contract, the failure SHALL be classified as an adapter contract mismatch.

#### Scenario: No valid identifier mapping produces an explicit boundary error
- **WHEN** a selected backend cannot derive a valid provider-native identifier from the shared request semantics
- **THEN** the provider adapter SHALL raise a contract error that identifies the backend and command family
- **THEN** the system MUST NOT defer that mismatch into an opaque downstream provider exception

### Requirement: Shared identifiers SHALL remain provider-neutral at the shared contract boundary
The system SHALL treat shared `symbol` and `symbols` fields as provider-neutral identifiers. Provider-native identifiers such as Eastmoney `quote_id` and Yahoo-specific ticker forms SHALL NOT be accepted as interchangeable shared input unless a shared capability explicitly declares that contract.

#### Scenario: Shared quote command rejects Eastmoney quote identifier input
- **WHEN** a user invokes a shared `quote.*` command with an Eastmoney `quote_id` such as `1.600519` in a shared `symbol` or `symbols` field
- **THEN** the request validation or adaptation layer SHALL reject the request with a readable contract error
- **THEN** the system SHALL NOT silently treat that provider-native identifier as a valid shared identifier

#### Scenario: Shared stock command accepts provider-neutral A-share symbol
- **WHEN** a user invokes a shared stock command with a provider-neutral A-share code such as `600519`
- **THEN** the normalized request SHALL preserve that provider-neutral identifier
- **THEN** any provider-native translation SHALL remain the responsibility of the selected provider adapter

### Requirement: Provider adapters SHALL own translation from shared identifiers to provider-native identifiers
When a concrete backend requires provider-native identifiers that differ from the shared contract, the selected provider adapter SHALL perform the translation before invoking the upstream API.

#### Scenario: Efinance quote latest translates shared symbols to quote identifiers
- **WHEN** a shared `quote.price.latest` request is dispatched to the `efinance` backend with provider-neutral symbols
- **THEN** the `efinance` adapter SHALL translate those symbols into Eastmoney `quote_id` values before calling the upstream callback
- **THEN** the user SHALL NOT be required to provide Eastmoney-native identifiers directly

#### Scenario: Yfinance A-share path translates provider-neutral code to Yahoo ticker
- **WHEN** a shared stock request targeting an A-share symbol is dispatched to the `yfinance` backend
- **THEN** the `yfinance` adapter SHALL translate the supported A-share code shape into a Yahoo ticker before invoking Yahoo data access
- **THEN** unsupported translation shapes SHALL fail locally with a contract error rather than being forwarded unchanged

