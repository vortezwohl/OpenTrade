## ADDED Requirements

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