# Backend Notes

This page records backend-specific operational notes that are too detailed for the top-level README.

## Auto backend behavior

- Shared commands default to `auto` when `--backend` is omitted.
- `auto` may choose different providers for different requests depending on market, symbol shape, and runtime failures.
- A command that ultimately succeeds under `auto` may still have failed on an earlier backend candidate.

## Shared symbols vs quote IDs

- Shared `symbol` / `symbols` are not Eastmoney `quote_id` values.
- `quote_id`-shaped values such as `0.000001` or `105.AAPL` should not be presented as generic shared symbols unless the command explicitly expects them.

## yfinance notes

- In this project, `yfinance` history/latest/profile flows are mostly single-symbol oriented.
- Shared symbols in `yfinance` follow Yahoo ticker semantics.
- Intraday history has hard windows:
  - `1m`: near 8 days
  - `5m` / `15m` / `30m`: near 60 days
  - `60m`: near 730 days
- For intraday requests, explicitly pass `start-date` and `end-date`, and keep the date span within the allowed window.
- `30m` is not purely native on the upstream side; yfinance internally requests `15m` and resamples.
- `Too Many Requests` / `YFRateLimitError` is a normal operational failure mode and may trigger fallback when `auto` is active.

## efinance notes

- Some realtime quote requests may succeed while related history backfill requests fail due to upstream Eastmoney endpoint instability.
- When observation output lacks `trace_points`, `current_metrics`, or enriched `recent_events`, inspect whether the command silently degraded after a failed history backfill.

## Practical troubleshooting order

1. Confirm whether the command ran under `auto`, `efinance`, `akshare`, or `yfinance`.
2. Separate parameter-validation failures from provider-execution failures.
3. For `observation` output, confirm whether history backfill and enrichment actually happened.
4. If needed, rerun with explicit `--backend` and `--view raw` to isolate the failing layer.