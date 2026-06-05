# provider-adapter-modularization Specification

## Purpose
TBD - created by archiving change refactor-provider-adapters-and-contracts. Update Purpose after archive.
## Requirements
### Requirement: Backend provider implementations SHALL be split into backend-specific modules
The `opentrade.backends` package SHALL no longer keep all provider implementations inside a single giant provider module. Each backend provider implementation SHALL live in its own module file under the `backends` package.

#### Scenario: Each backend has an isolated implementation module
- **WHEN** the backend package is organized for provider construction and adaptation
- **THEN** efinance, akshare, and yfinance provider implementations SHALL each be defined in separate module files under `opentrade/backends`
- **THEN** no single file SHALL remain responsible for all backend-specific handlers, request translation, and result standardization logic at once

### Requirement: Shared provider helpers SHALL be separated from backend-specific logic
Cross-backend helper functions SHALL live in dedicated common helper modules, while backend-native request translation, identifier mapping, and response interpretation SHALL remain in backend-specific modules.

#### Scenario: Common helpers exclude backend-native request semantics
- **WHEN** a helper is placed in a shared provider common module
- **THEN** that helper MUST be genuinely reusable across multiple backends, such as generic request value extraction or generic contract normalization support
- **THEN** backend-native logic such as efinance market mappings, Yahoo ticker translation, or akshare catalog column interpretation MUST remain in backend-specific modules

### Requirement: Provider factory interfaces SHALL remain stable across modularization
Internal module splitting SHALL NOT leak new file-layout knowledge into upper execution layers. The backend factory SHALL remain the stable registration and lookup facade for provider instances.

#### Scenario: Upper layers still resolve providers through the factory
- **WHEN** executor, facade, or command registration code needs a backend provider
- **THEN** it SHALL continue to obtain providers through the backend factory interfaces
- **THEN** upper layers MUST NOT import backend-specific implementation modules directly only because the internal layout was modularized

### Requirement: Modularization SHALL preserve behavior before contract changes are applied
The first modularization step SHALL be verifiable as a structural refactor that preserves existing behavior before later contract-tightening behavior changes are introduced.

#### Scenario: Module split is independently verifiable
- **WHEN** provider code is first moved from the giant provider module into backend-specific modules
- **THEN** the refactor step SHALL be testable without simultaneously depending on every later contract change
- **THEN** subsequent contract and routing changes SHALL be introduced as separate verifiable steps on top of the modularized structure

