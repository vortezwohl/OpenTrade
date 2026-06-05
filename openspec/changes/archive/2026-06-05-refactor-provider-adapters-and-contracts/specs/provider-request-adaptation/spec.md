## ADDED Requirements

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