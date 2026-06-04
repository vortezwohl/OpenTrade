## ADDED Requirements

### Requirement: Internal execution controls must not leak into provider kwargs
The system SHALL keep execution-time control data separate from provider-native request kwargs. Internal control fields such as runtime execution limits MUST NOT be forwarded to third-party SDK callbacks unless the current adapter branch explicitly consumes that control as part of its own implementation.

#### Scenario: Generic efinance passthrough command receives display limit
- **WHEN** a shared or generated efinance command that does not implement provider-side limit optimization is executed with `--limit`
- **THEN** the third-party callback SHALL receive sanitized kwargs without internal control fields such as `__runtime_limit__`
- **THEN** the command MAY still apply output trimming or metadata recording locally, but it MUST NOT fail with `unexpected keyword argument '__runtime_limit__'`

#### Scenario: Provider-optimized limit path consumes execution control explicitly
- **WHEN** a command path explicitly supports provider-side execution limit optimization
- **THEN** the adapter SHALL consume the execution limit from execution context or a sanitized internal channel before invoking the third-party callback
- **THEN** the command metadata SHALL indicate whether the execution limit was actually applied at provider-request level
