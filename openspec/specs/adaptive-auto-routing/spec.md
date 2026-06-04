# adaptive-auto-routing Specification

## Purpose
TBD - created by archiving change fix-shared-command-routing-and-adaptation. Update Purpose after archive.
## Requirements
### Requirement: Auto backend planning SHALL use normalized request semantics
The system SHALL derive auto backend candidate order after shared request normalization, using command capability, market semantics, and identifier shape rather than a single static global candidate order for all shared commands.

#### Scenario: A-share shared request prefers the strongest local market backend first
- **WHEN** a shared command targets A-share semantics or a local quote identifier shape that maps to domestic market data
- **THEN** auto backend planning SHALL rank the strongest local market backend ahead of less suitable candidates

#### Scenario: US ticker shared request prefers the Yahoo-oriented backend first
- **WHEN** a shared command targets a US ticker or explicit US market semantics
- **THEN** auto backend planning SHALL rank the Yahoo-oriented backend ahead of domestic-market-first backends

### Requirement: Auto planning SHALL remain request-aware across watch iterations
The system SHALL preserve request-aware auto planning for every execution cycle, including watch mode, instead of falling back to a static precomputed candidate chain that ignores normalized request semantics.

#### Scenario: Watch mode rebuilds or reuses the same request-aware candidate semantics
- **WHEN** a shared auto-routed command runs in watch mode for multiple iterations
- **THEN** each iteration SHALL use the same request-aware backend planning semantics as a normal single execution

### Requirement: Auto execution SHALL expose candidate planning and final resolution metadata
The system SHALL expose enough metadata for raw output and regression reports to distinguish requested backend, planned candidate order, attempted candidates, final backend, and whether the final result required fallback.

#### Scenario: Raw output records final backend after fallback
- **WHEN** an auto-routed shared command succeeds on a non-first candidate
- **THEN** raw metadata SHALL identify the planned candidate order and the final backend that produced the successful result

#### Scenario: Raw output records unresolved auto chain when no candidate succeeds
- **WHEN** an auto-routed shared command fails before any candidate completes successfully
- **THEN** raw metadata and regression output SHALL record that no final backend was reached

