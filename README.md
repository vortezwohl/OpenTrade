<div align="center">
  <h1>OpenTrade</h1>
  <p><strong>Market data in your terminal, shaped for humans and agents.</strong></p>
  <p>Search instruments, inspect quotes, review history, export datasets, and read indicator-rich <code>observation</code> output from one consistent command tree.</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/opentrade/"><img alt="PyPI package" src="https://img.shields.io/badge/PyPI-opentrade-2563EB"></a>
    <a href="https://pypi.org/project/akshare/"><img alt="Backend akshare" src="https://img.shields.io/badge/Backend-akshare-1D4ED8"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="Backend efinance" src="https://img.shields.io/badge/Backend-efinance-B45309"></a>
    <a href="https://pypi.org/project/yfinance/"><img alt="Backend yfinance" src="https://img.shields.io/badge/Backend-yfinance-15803D"></a>
  </p>
  <p>
    <a href="#installation">Installation</a> ·
    <a href="#agent-skills">Agent Skills</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#command-tree">Command tree</a> ·
    <a href="#output-and-defaults">Output and defaults</a> ·
    <a href="#indicator-support">Indicator support</a> ·
    <a href="#more-docs">More docs</a>
  </p>
</div>

<p align="center"><strong>English | <a href="i18n/README.zh-CN.md">简体中文</a> | <a href="i18n/README.zh-TW.md">繁體中文</a></strong></p>

## Installation

Install the published PyPI package `opentrade`. The package exposes both `opentrade` and `optr`.

```bash
uv add -U opentrade
opentrade --help
```

```bash
pip install -U opentrade
opentrade --help
```

Python `3.10+` is required.

## Agent Skills

OpenTrade also provides agent skills for automated investment research workflows.

When you want Codex, Claude Code, or another coding agent to install them, just say:

> Please install skills from `https://github.com/vortezwohl/OpenTrade`, and place them in my global user skill directory.

These skills are designed for automated research across stocks, funds, bonds, futures, and broader market workflows.

## Quick Start

### 1. Search

```bash
opentrade search --query AAPL --market US_stock --result-count 5 --format json
```

Use this when you only know a ticker, keyword, or company name.

### 2. Latest quote

```bash
opentrade quote price latest --symbols AAPL --format json
```

Use shared `quote` commands when you want a cross-backend symbol or ticker workflow.

### 3. History

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

Use history commands when you need candles, backfill, indicators, or exports.

## Command Tree

| Command | Role | Typical use |
|---|---|---|
| `search` | Keyword-based discovery | Find candidates before you know the exact identifier |
| `resolve` | Identifier resolution | Turn a symbol into a provider-specific quote ID when needed |
| `quote` | Cross-asset shared queries | Shared latest, history, and profile access |
| `stock` | Stock-specific workflows | Price, snapshot, flow, holders, profile |
| `fund` | Fund-specific workflows | NAV history, estimates, allocation, managers, reports |
| `bond` | Bond-specific workflows | Price, profile, trades, flows |
| `futures` | Futures-specific workflows | Catalog, history, live quotes, trades |
| `market` | Market-level queries | Live scans and mapping-style lookups |
| `watch` | Refresh wrapper | Repeat a supported command on an interval |

## Output and Defaults

Current real defaults for shared commands:

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`
- omitted `--backend` resolves to `auto`

Practical notes:

- `observation` is the default public-facing view.
- Use `--view raw` when you want the unwrapped payload shape.
- `json` is usually the best target for scripts and agents.
- `full` gives richer indicator context than `advanced`, but it costs more backfill and computation.

## Indicator Support

Indicator enrichment is a core part of `opentrade` and remains available on compatible commands.

| Level | What it gives you in practice |
|---|---|
| `basic` | Core trend and momentum coverage such as MA, EMA, MACD, RSI, KDJ, BOLL, ATR, and OBV |
| `advanced` | Broader trend-strength, channel, and money-flow coverage such as ADX, Donchian, Keltner, SuperTrend, MFI, PVT, CMF, VWAP, VR, and PSY |
| `full` | Richer structure and market-context layers such as Ichimoku, SAR, Mass Index, Pivot Points, Fibonacci Retracement, support/resistance, Chaikin Oscillator, Chaikin Volatility, and EMV |

Representative indicator families:

- Moving averages and base transforms
- Trend and channel indicators
- Momentum indicators
- Volume and money-flow indicators
- Volatility indicators
- Price-structure indicators
- Common Chinese-market technical indicators

See [docs/indicator-coverage.md](docs/indicator-coverage.md) for the fuller list and grouping.

## Backend Notes

- Shared commands default to `auto`, and `auto` may fall back when an earlier backend candidate fails.
- Shared `symbols` are not Eastmoney `quote_id` values.
- `yfinance` intraday history has strict window limits and is mostly single-symbol oriented in this project.
- A command that succeeds under `auto` may still have lost enriched observation fields after a failed history backfill on the chosen backend.

See [docs/backend-notes.md](docs/backend-notes.md) for deeper backend-specific constraints and troubleshooting notes.

## Common Tasks

### Search and inspect

```bash
opentrade search --query NVDA --market US_stock
opentrade quote price latest --symbols NVDA
```

### Review history

```bash
opentrade stock price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

### Watch quotes

```bash
opentrade watch --interval 5 --count 3 quote price latest --symbols AAPL --format json
```

### Export data

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format csv --output aapl-history.csv
```

## More Docs

- [Indicator coverage](docs/indicator-coverage.md)
- [Observation examples](docs/observation-examples.md)
- [Backend notes](docs/backend-notes.md)
- [简体中文 README](i18n/README.zh-CN.md)
- [繁體中文 README](i18n/README.zh-TW.md)

## License

MIT License.
