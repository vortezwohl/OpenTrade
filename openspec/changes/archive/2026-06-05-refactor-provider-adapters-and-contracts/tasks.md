## 1. Provider Module Split

- [x] 1.1 Define the target `opentrade/backends` module layout for backend-specific provider modules and shared provider helper modules.
- [x] 1.2 Move backend-agnostic helper functions from `providers.py` into a common helper module without changing behavior.
- [x] 1.3 Move efinance-specific handlers, request translation, and provider construction into an efinance backend module.
- [x] 1.4 Move akshare-specific handlers, request translation, and provider construction into an akshare backend module.
- [x] 1.5 Move yfinance-specific handlers, request translation, and provider construction into a yfinance backend module.
- [x] 1.6 Update `factory.py` and `backends/__init__.py` so upper layers still resolve providers through stable factory interfaces.
- [x] 1.7 Add or update tests that verify the module split preserves provider registration and existing baseline behavior.

## 2. Shared Contract Truth

- [x] 2.1 Audit shared command schemas for provider-neutral field semantics versus backend-native parameter leakage.
- [x] 2.2 Tighten shared support matrices so backend listings reflect real market support and cardinality support.
- [x] 2.3 Define explicit shared identifier semantics for `stock.*` and `quote.*` command families.
- [x] 2.4 Decide and encode the contract for ambiguous `quote.*` identifiers so Eastmoney quote IDs and Yahoo tickers are no longer treated as silently interchangeable.
- [x] 2.5 Update request validation and adapter boundaries so unsupported identifier shapes fail as explicit contract mismatches.

## 3. Backend-Specific Adaptation

- [x] 3.1 Implement explicit A-share to Yahoo ticker translation or explicit rejection in the yfinance stock adapter paths.
- [x] 3.2 Refine efinance-specific market and identifier adaptation so shared semantics are translated only inside the efinance module.
- [x] 3.3 Refine akshare-specific request and catalog adaptation so field interpretation stays local to the akshare module.
- [x] 3.4 Remove or reduce any remaining direct third-party callback passthroughs that still depend on provider-neutral requests being backend-native.
- [x] 3.5 Add targeted provider adapter tests for identifier translation, market support, and single-value versus multi-value enforcement.

## 4. Routing And Verification

- [x] 4.1 Update auto-routing inputs to depend on truthful normalized shared capability data after contract tightening.
- [x] 4.2 Update command catalog and request schema tests so they assert truthful backend support and cardinality semantics instead of legacy assumptions.
- [x] 4.3 Update regression-oriented tests for `quote.*`, `stock.*`, and `fund.profile` command families to cover the tightened shared contracts.
- [x] 4.4 Run the relevant local test slices and verify that structural module split changes are separated from intentional contract-behavior changes.