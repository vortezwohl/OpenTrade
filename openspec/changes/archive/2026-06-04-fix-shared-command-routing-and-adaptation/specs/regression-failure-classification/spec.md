## ADDED Requirements

### Requirement: Real regression reports SHALL classify failures by layer
The real regression framework SHALL classify failed or degraded executions into at least distinct categories for sample mismatch, adapter gap, product defect, and upstream instability, rather than treating all non-pass outcomes as one undifferentiated failure pool.

#### Scenario: Date sample mismatch is classified separately from product defect
- **WHEN** a regression case fails because the test sample format does not satisfy the provider contract while the product path is otherwise behaving as designed
- **THEN** the regression result SHALL classify that outcome as sample mismatch rather than product defect

#### Scenario: Shared semantic to provider mismatch is classified as adaptation gap
- **WHEN** a regression case fails because the shared contract and provider adaptation layer disagree on the meaning of an input such as market semantics
- **THEN** the regression result SHALL classify that outcome as adapter gap

### Requirement: Regression artifacts SHALL preserve routing and classification evidence
The real regression framework SHALL preserve enough structured evidence to explain failure classification, including requested backend, candidate planning, final backend, command family, runtime tags, and artifact metadata.

#### Scenario: Auto timeout retains unresolved routing evidence
- **WHEN** an auto-routed regression case times out before any final backend is reached
- **THEN** the regression artifact SHALL preserve routing evidence showing the unresolved final backend state and the command's classification inputs

#### Scenario: Report summary distinguishes product issues from sample issues
- **WHEN** regression summaries are rendered for human review
- **THEN** the summary SHALL distinguish counts attributable to product defects from counts attributable to sample mismatch or adaptation gaps

### Requirement: Test suites SHALL validate behavior instead of freezing obsolete candidate order
The automated test suite SHALL validate semantic routing and adaptation outcomes rather than hard-coding obsolete static auto candidate order or provider-native shared field names as the expected long-term behavior.

#### Scenario: Auto routing tests assert request-aware ordering semantics
- **WHEN** tests cover auto backend planning
- **THEN** they SHALL assert the semantic routing outcome for representative request classes instead of asserting one static order for all shared commands

#### Scenario: Shared schema tests assert normalized field meaning
- **WHEN** tests cover shared request validation
- **THEN** they SHALL assert normalized semantic fields and validation behavior instead of requiring provider-native internal parameter names as the primary contract
