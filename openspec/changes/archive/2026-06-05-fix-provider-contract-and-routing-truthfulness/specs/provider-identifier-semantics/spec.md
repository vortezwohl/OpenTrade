## ADDED Requirements

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