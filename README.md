<div align="center">
  <h1>efinance-cli</h1>
  <p><strong>Market data in your terminal, shaped for humans, scripts, and agents.</strong></p>
  <p>Search instruments, resolve quote IDs, inspect live quotes, review history, export datasets, and read indicator-rich <code>observation</code> output from one consistent command tree.</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/the-efinance-cli/"><img alt="PyPI package" src="https://img.shields.io/badge/PyPI-the--efinance--cli-2563EB"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="Upstream efinance" src="https://img.shields.io/badge/Upstream-efinance-B45309"></a>
    <img alt="Default view observation" src="https://img.shields.io/badge/Default%20View-observation-0F766E">
    <img alt="Indicator enrichment" src="https://img.shields.io/badge/Indicators-basic%20%7C%20advanced%20%7C%20full-7C3AED">
  </p>
  <p>
    <a href="#installation">Installation</a> ·
    <a href="#thirty-second-start">30-second start</a> ·
    <a href="#command-map">Command map</a> ·
    <a href="#output-model">Output model</a> ·
    <a href="#indicator-coverage">Indicator coverage</a> ·
    <a href="#observation-examples">Observation examples</a>
  </p>
</div>

<p align="center"><strong>English | <a href="i18n/README.zh-CN.md">简体中文</a> | <a href="i18n/README.zh-TW.md">繁體中文</a></strong></p>

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>Discoverable</strong><br />
      A task-shaped command tree makes it easier to find the right entrypoint than browsing raw upstream functions.
    </td>
    <td width="33%" valign="top">
      <strong>Readable</strong><br />
      The CLI keeps terminal output consistent across <code>table</code>, <code>json</code>, <code>csv</code>, and <code>tsv</code>, with <code>observation</code> as the default view.
    </td>
    <td width="33%" valign="top">
      <strong>Indicator-rich</strong><br />
      Compatible commands can be enriched with a broad built-in technical-indicator set for screening, review, and downstream analysis.
    </td>
  </tr>
</table>

<a id="installation"></a>
## Installation

Install the published PyPI package `the-efinance-cli`. The package exposes both `efinance` and `efi`.

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>uv</strong>
      <pre lang="bash"><code>uv add -U the-efinance-cli
efinance --help</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>pip</strong>
      <pre lang="bash"><code>pip install -U the-efinance-cli
efinance --help</code></pre>
    </td>
  </tr>
</table>

Python `3.10+` is required.

<a id="what-this-tool-is"></a>
## What This Tool Is

> `efinance-cli` is a product layer on top of `efinance`, not a loose script collection.

It reorganizes upstream capability into a public command tree that is easier to browse from a terminal, easier to automate from scripts, and easier to consume in structured output. The goal is not to replace the upstream market-data library. The goal is to make that capability more stable and more usable from a CLI.

<a id="thirty-second-start"></a>
## 30-Second Start

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>1. Search first</strong>
      <pre lang="bash"><code>efinance search --query AAPL --market US_stock --result-count 5 --format json</code></pre>
      Start here when you only know a ticker, keyword, or company name.
    </td>
    <td width="33%" valign="top">
      <strong>2. Resolve <code>quote_id</code></strong>
      <pre lang="bash"><code>efinance resolve quote-id --symbol AAPL --market us_stock --format json</code></pre>
      Common US instruments resolve into identifiers such as <code>105.AAPL</code>.
    </td>
    <td width="33%" valign="top">
      <strong>3. Query market data</strong>
      <pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format json</code></pre>
      Continue from there into history, latest quotes, watch loops, and export workflows.
    </td>
  </tr>
</table>

<a id="main-functions"></a>
## Main Functions

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>Instrument discovery</strong>
      <ul>
        <li>Search instruments by keyword.</li>
        <li>Resolve symbols into <code>quote_id</code>.</li>
        <li>Move from discovery into quote and history queries without switching tools.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>Cross-asset data access</strong>
      <ul>
        <li>Query stocks, funds, bonds, futures, and market-level live data.</li>
        <li>Read both latest quotes and historical series.</li>
        <li>Run refresh loops with one shared watch model.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>Structured output</strong>
      <ul>
        <li>Export as <code>table</code>, <code>json</code>, <code>csv</code>, or <code>tsv</code>.</li>
        <li>Use <code>observation</code> as the default public-facing view.</li>
        <li>Fallback to <code>raw</code> when downstream consumers need the unwrapped shape.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>Indicator enrichment</strong>
      <ul>
        <li>Choose <code>basic</code>, <code>advanced</code>, or <code>full</code>.</li>
        <li>Expose trend, momentum, volatility, volume, and structure indicators.</li>
        <li>Produce richer market context for review, screening, and automation.</li>
      </ul>
    </td>
  </tr>
</table>

<a id="command-map"></a>
## Command Map

<table>
  <thead>
    <tr>
      <th align="left">Top-level command</th>
      <th align="left">Role</th>
      <th align="left">Typical use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>search</code></td>
      <td>Keyword-based discovery.</td>
      <td>Find candidates before you know the exact identifier.</td>
    </tr>
    <tr>
      <td><code>resolve</code></td>
      <td>Identifier resolution.</td>
      <td>Turn a symbol into a reusable <code>quote_id</code>.</td>
    </tr>
    <tr>
      <td><code>quote</code></td>
      <td>Cross-asset quote access.</td>
      <td>Use when the <code>quote_id</code> is already known.</td>
    </tr>
    <tr>
      <td><code>market</code></td>
      <td>Market-level queries.</td>
      <td>Run live scans and market-mapping style lookups.</td>
    </tr>
    <tr>
      <td><code>stock</code></td>
      <td>Stock-oriented queries.</td>
      <td>History, snapshots, live lists, flows, holders, and profiles.</td>
    </tr>
    <tr>
      <td><code>fund</code></td>
      <td>Fund-oriented queries.</td>
      <td>NAV history, live estimates, allocation, managers, and reports.</td>
    </tr>
    <tr>
      <td><code>bond</code></td>
      <td>Bond-oriented queries.</td>
      <td>Profiles, price history, live lists, trades, and flows.</td>
    </tr>
    <tr>
      <td><code>futures</code></td>
      <td>Futures-oriented queries.</td>
      <td>Catalog, history, live quotes, and trade detail.</td>
    </tr>
    <tr>
      <td><code>watch</code></td>
      <td>Refresh wrapper.</td>
      <td>Repeat a supported subcommand on a shared polling loop.</td>
    </tr>
  </tbody>
</table>

<a id="output-model"></a>
## Output Model

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>Current real defaults</strong>
      <ul>
        <li><code>--format table</code></li>
        <li><code>--indicator-level advanced</code></li>
        <li><code>--view observation</code></li>
        <li><code>--trace-window 32</code></li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>Practical notes</strong>
      <ul>
        <li><code>observation</code> is the default public-facing view.</li>
        <li>Pass <code>--view raw</code> when you want the unwrapped payload shape.</li>
        <li><code>json</code> is usually the best target for downstream programs.</li>
        <li><code>full</code> gives richer indicator context than <code>advanced</code>, but costs more work.</li>
      </ul>
    </td>
  </tr>
</table>

<table>
  <thead>
    <tr>
      <th align="left">Output or runtime flag</th>
      <th align="left">Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>--format table|json|csv|tsv</code></td>
      <td>Choose terminal view or export-friendly structured output.</td>
    </tr>
    <tr>
      <td><code>--full</code></td>
      <td>Print more complete result content.</td>
    </tr>
    <tr>
      <td><code>--transpose</code></td>
      <td>Transpose tabular output for easier terminal reading in some cases.</td>
    </tr>
    <tr>
      <td><code>--no-index</code></td>
      <td>Hide row indices in table output.</td>
    </tr>
    <tr>
      <td><code>--limit N</code></td>
      <td>Keep only the first <code>N</code> rows in the rendered result.</td>
    </tr>
    <tr>
      <td><code>--output PATH</code></td>
      <td>Write the rendered result to a file.</td>
    </tr>
    <tr>
      <td><code>--encoding utf-8</code></td>
      <td>Set file-output encoding.</td>
    </tr>
    <tr>
      <td><code>--watch --interval --count --clear/--no-clear</code></td>
      <td>Run supported commands on a refresh loop.</td>
    </tr>
  </tbody>
</table>

<a id="indicator-coverage"></a>
## Indicator Coverage

`efinance-cli` ships with a broad built-in indicator set. Compatible commands can expose far more than raw quotes, which makes the CLI useful for screening, review, and downstream analytics.

<details open>
<summary><strong>Moving averages and base transforms</strong></summary>
<p><code>sma</code> · <code>ema</code> · <code>rma</code> · <code>wma</code> · <code>dema</code> · <code>tema</code> · <code>trima</code> · <code>hma</code> · <code>zlema</code> · <code>highest</code> · <code>lowest</code> · <code>median_price</code> · <code>typical_price</code> · <code>true_range</code></p>
</details>

<details open>
<summary><strong>Trend and channel indicators</strong></summary>
<p><code>macd</code> · <code>bollinger_bands</code> · <code>donchian_channel</code> · <code>keltner_channel</code> · <code>moving_average_envelope</code> · <code>aroon_indicator</code> · <code>dmi</code> · <code>adx</code> · <code>supertrend</code> · <code>parabolic_sar</code> · <code>ichimoku_cloud</code></p>
</details>

<details open>
<summary><strong>Momentum indicators</strong></summary>
<p><code>momentum</code> · <code>roc</code> · <code>rsi</code> · <code>stochastic_oscillator</code> · <code>kdj</code> · <code>cci</code> · <code>williams_r</code> · <code>trix</code> · <code>tsi</code> · <code>ultimate_oscillator</code> · <code>dpo</code> · <code>ppo</code></p>
</details>

<details open>
<summary><strong>Volume and money-flow indicators</strong></summary>
<p><code>obv</code> · <code>accumulation_distribution</code> · <code>chaikin_money_flow</code> · <code>chaikin_oscillator</code> · <code>mfi</code> · <code>vwap</code> · <code>force_index</code> · <code>ease_of_movement</code> · <code>price_volume_trend</code> · <code>volume_ratio</code></p>
</details>

<details open>
<summary><strong>Volatility indicators</strong></summary>
<p><code>atr</code> · <code>natr</code> · <code>historical_volatility</code> · <code>chaikin_volatility</code> · <code>mass_index</code></p>
</details>

<details open>
<summary><strong>Price-structure indicators</strong></summary>
<p><code>pivot_points</code> · <code>fibonacci_retracement</code> · <code>rolling_support_resistance</code></p>
</details>

<details open>
<summary><strong>Common Chinese-market technical indicators</strong></summary>
<p><code>bias</code> · <code>bbi</code> · <code>psy</code> · <code>vr</code> · <code>mtm</code> · <code>dma</code> · <code>brar</code> · <code>cr</code> · <code>emv</code> · <code>asi</code></p>
</details>

<table>
  <thead>
    <tr>
      <th align="left">Level</th>
      <th align="left">What it gives you in practice</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>basic</code></td>
      <td>The core trend and momentum set such as MA, EMA, MACD, RSI, KDJ, BOLL, ATR, and OBV.</td>
    </tr>
    <tr>
      <td><code>advanced</code></td>
      <td>Broader trend-strength, channel, and money-flow coverage such as ADX, Donchian, Keltner, SuperTrend, MFI, PVT, CMF, VWAP, VR, and PSY.</td>
    </tr>
    <tr>
      <td><code>full</code></td>
      <td>Richer structure and market-context layers such as Ichimoku, SAR, Mass Index, Pivot Points, Fibonacci Retracement, support/resistance, ADL, Chaikin Oscillator, Chaikin Volatility, and EMV.</td>
    </tr>
  </tbody>
</table>

<a id="observation-examples"></a>
## Observation Examples

The examples below only show the public-facing `observation` format.

<details open>
<summary><strong>Latest quote observation</strong></summary>

<p><strong>Command</strong></p>
<pre lang="bash"><code>efinance quote price latest --quote-ids 105.AAPL --format table --indicator-level full --trace-window 4</code></pre>

<p><strong>Typical output</strong></p>

```text
+-----------------------------+
| meta                        |
+-----------------------------+
| module: common              |
| function: get_quote_history |
| view: observation           |
| indicator_level: full       |
| trace_window: 4             |
| row_count: 4                |
| code: AAPL                  |
| name: Apple Inc.            |
| as_of: 2026-05-28           |
+-----------------------------+

+------------------+
| latest_quote     |
+------------------+
| code: AAPL       |
| name: Apple Inc. |
| date: 2026-05-28 |
| close: 106       |
| open: 105        |
| high: 107        |
| low: 104         |
| volume: 1700     |
+------------------+

+---------------------+
| current_metrics     |
+---------------------+
| close: 106          |
| open: 105           |
| high: 107           |
| low: 104            |
| volume: 1700        |
| ma5: 103            |
| ma10: 102.5         |
| macd_dif: 0.36      |
| macd_dea: 0.26      |
| rsi14: 59           |
+---------------------+

+-----------------------------------+
| trace_points.price_ma             |
+-----------------------------------+
| [block 1] bar_offset: -3 -> 0     |
| bar_offset: -3 | -2 | -1 | 0      |
| close: 100 | 102 | 104 | 106      |
| ma5: 99.8 | 100.5 | 102 | 103     |
| ma10: 100.1 | 100.4 | 101 | 102.5 |
+-----------------------------------+

+-------------------------------------------------------------+
| recent_events                                               |
+-------------------------------------------------------------+
| [1] bars_ago: -2                                            |
|     event_key: ma5_crossed_above_ma10                       |
|     subject_a: ma5                                          |
|     relation: crossed_above                                 |
|     subject_b: ma10                                         |
|     description: ma5 moved from below to above ma10         |
| prev_a: 99.8   prev_b: 100.1   curr_a: 100.5   curr_b:      |
| 100.4                                                     |
+-------------------------------------------------------------+
```

</details>

<details open>
<summary><strong>History observation</strong></summary>

<p><strong>Command</strong></p>
<pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format table --indicator-level advanced --trace-window 4</code></pre>

<p><strong>Typical output</strong></p>

```text
+-----------------------------+
| meta                        |
+-----------------------------+
| module: common              |
| function: get_quote_history |
| view: observation           |
| indicator_level: full       |
| trace_window: 4             |
| row_count: 4                |
| code: AAPL                  |
| name: Apple Inc.            |
| as_of: 2026-05-28           |
+-----------------------------+

+---------------------+
| current_metrics     |
+---------------------+
| close: 106          |
| ma5: 103            |
| ma10: 102.5         |
| ma20: 101.4         |
| ema12: 102.9        |
| ema26: 101.7        |
| macd_dif: 0.36      |
| macd_dea: 0.26      |
| rsi14: 59           |
| kdj_k: 62           |
| kdj_d: 60           |
| plus_di: 28         |
| minus_di: 16        |
| adx: 28             |
+---------------------+

+---------------------------------------+
| trace_points.macd_osc                 |
+---------------------------------------+
| [block 1] bar_offset: -3 -> 0         |
| bar_offset: -3 | -2 | -1 | 0          |
| macd_dif: 0.05 | 0.2 | 0.28 | 0.36    |
| macd_dea: -0.02 | 0.08 | 0.18 | 0.26  |
| rsi14: 51 | 54 | 56 | 59              |
| kdj_k: 50 | 55 | 60 | 62              |
| kdj_d: 47 | 52 | 57 | 60              |
+---------------------------------------+

+-------------------------------------------------------------+
| recent_events                                               |
+-------------------------------------------------------------+
| [1] bars_ago: 0                                             |
|     event_key: volume_ratio_5_crossed_above_1               |
|     subject_a: volume_ratio_5                               |
|     relation: crossed_above                                 |
|     subject_b: 1.0                                          |
|     description: volume_ratio_5 moved from at-or-below to   |
|     above 1                                                 |
| prev_a: 1   prev_b: 1   curr_a: 1.3   curr_b: 1             |
+-------------------------------------------------------------+
```

</details>

<details open>
<summary><strong>Multi-source fund observation</strong></summary>

<p><strong>Command</strong></p>
<pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format table --view observation --trace-window 4</code></pre>

<p><strong>Typical output</strong></p>

```text
+---------------+
| source.161725 |
+---------------+

+-----------------------------+
| meta                        |
+-----------------------------+
| module: common              |
| function: get_quote_history |
| view: observation           |
| indicator_level: full       |
| trace_window: 4             |
| row_count: 4                |
| code: AAPL                  |
| name: Apple Inc.            |
| as_of: 2026-05-28           |
+-----------------------------+

+------------------+
| latest_quote     |
+------------------+
| code: AAPL       |
| name: Apple Inc. |
| date: 2026-05-28 |
| close: 106       |
+------------------+

+---------------+
| source.005827 |
+---------------+

+-----------------------------+
| meta                        |
+-----------------------------+
| module: common              |
| function: get_quote_history |
| view: observation           |
| indicator_level: full       |
| trace_window: 4             |
| row_count: 4                |
| code: AAPL                  |
| name: Apple Inc.            |
| as_of: 2026-05-28           |
+-----------------------------+

+------------------+
| latest_quote     |
+------------------+
| code: AAPL       |
| name: Apple Inc. |
| date: 2026-05-28 |
| close: 106       |
+------------------+
```

</details>

<a id="common-workflows"></a>
## Common Workflows

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>Search and inspect</strong>
      <pre lang="bash"><code>efinance search --query NVDA --market US_stock
efinance resolve quote-id --symbol NVDA --market us_stock
efinance quote price latest --quote-ids 105.NVDA</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>Watch a quote</strong>
      <pre lang="bash"><code>efinance watch --interval 5 --count 3 quote price latest --quote-ids 105.AAPL --format json</code></pre>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>Batch fund history</strong>
      <pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format json</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>Market-level live scan</strong>
      <pre lang="bash"><code>efinance market price live --market m:105+t:3 --format json</code></pre>
    </td>
  </tr>
</table>

<a id="yahoo-finance-backend"></a>
## Yahoo Finance Backend

`yfinance` is now a first-class backend for a focused subset of shared commands. Use `--backend yfinance` when you want Yahoo Finance data explicitly, and keep the following boundaries in mind:

- Supported shared coverage includes search, stock and quote history, quote latest, conditional stock latest/snapshot, stock and quote profile, fund NAV history, and fund profile.
- Yahoo-only capability currently starts with `quote news`, exposed as a provider-extension command instead of pretending to be backend-agnostic.
- Symbol semantics follow Yahoo tickers first. Typical inputs are `AAPL`, `MSFT`, `0700.HK`, or `9988.HK`; not every domestic-market symbol style can be inferred safely.
- Live smoke verification is intentionally optional because Yahoo may return explicit rate-limit failures even for valid requests.

```bash
efinance search --query AAPL --backend yfinance --format json
efinance quote price latest --quote-ids AAPL --backend yfinance --format json
efinance quote news --quote-id AAPL --result-count 5 --format json
```

<a id="notes"></a>
## Notes

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>Data-source boundaries</strong>
      <ul>
        <li>The CLI depends on upstream market-data availability.</li>
        <li>Realtime stability depends on network conditions and source-side behavior.</li>
        <li>Some commands support richer indicator enrichment than others.</li>
        <li><code>yfinance</code>-backed commands use Yahoo ticker / symbol semantics and may fail with explicit rate-limit errors.</li>
        <li>Optional live smoke checks should be run manually against a small symbol set because Yahoo throttling makes them non-deterministic.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>Usage boundaries</strong>
      <ul>
        <li>Use side-effect commands such as report download intentionally.</li>
        <li>Prefer <code>json</code> when another program will consume the result.</li>
        <li>Prefer <code>observation</code> when a human or agent needs concise market context instead of raw tables.</li>
      </ul>
    </td>
  </tr>
</table>

<a id="license"></a>
## License

See [LICENSE](LICENSE).
