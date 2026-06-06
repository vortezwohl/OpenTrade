# Observation Examples

This page keeps longer `observation` examples out of the README while preserving a concrete reference for the public-facing output shape.

## Latest quote observation

### Command

```bash
opentrade quote price latest --symbols AAPL --format table --indicator-level full --trace-window 4
```

### Typical sections

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points.*`
- `recent_events`

## History observation

### Command

```bash
opentrade stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format table --indicator-level advanced --trace-window 4
```

### Typical sections

- `meta`
- `current_metrics`
- `trace_points.*`
- `recent_events`

## Multi-source observation

### Command

```bash
opentrade fund nav history-batch --symbols 161725 --symbols 005827 --format table --view observation --trace-window 4
```

### Typical sections

- `source.<key>`
- nested `meta`
- nested `latest_quote`
- nested `current_metrics`
- nested `trace_points.*`
- nested `recent_events`

## Reading notes

- `observation` is the default public-facing view for compatible shared commands.
- `raw` is better when a downstream consumer needs the unwrapped provider or standard-result shape.
- Empty `recent_events` does not always mean “no signal”; in some paths it can also indicate that history backfill or enrichment did not complete.