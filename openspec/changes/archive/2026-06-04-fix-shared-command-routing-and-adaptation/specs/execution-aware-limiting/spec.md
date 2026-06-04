## ADDED Requirements

### Requirement: Limit behavior SHALL distinguish display truncation from execution reduction
The system SHALL distinguish between result display truncation and true execution reduction. Command execution metadata and regression outputs SHALL make that distinction explicit whenever a limit is provided.

#### Scenario: Display-only limit is reported as non-reducing
- **WHEN** a command applies `--limit` only after full data retrieval
- **THEN** the system SHALL report that the limit affected display output only and did not reduce upstream execution scope

#### Scenario: Execution-aware limit is reported as applied
- **WHEN** a command can translate `--limit` into an upstream page size, request bound, or lightweight fetch path
- **THEN** the system SHALL report that execution-aware limiting was applied

### Requirement: Heavy command families SHALL declare an execution-limiting strategy
The system SHALL define an execution-limiting strategy for heavy shared command families that are known to perform large fetches or multi-page scans. That strategy SHALL specify whether the command supports upstream reduction, adapter-level lightweight fetch, or display-only truncation.

#### Scenario: Market live command declares its limit strategy
- **WHEN** the command catalog exposes a heavy market live command
- **THEN** the command metadata or adaptation layer SHALL declare whether its limit is execution-aware or display-only

#### Scenario: Futures or quote heavy path does not silently pretend to reduce work
- **WHEN** a heavy futures or quote command cannot reduce upstream work despite receiving `--limit`
- **THEN** the system SHALL preserve correct results while explicitly marking the limit as display-only
