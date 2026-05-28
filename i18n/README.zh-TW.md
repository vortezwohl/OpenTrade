<div align="center">
  <h1>efinance-cli</h1>
  <p><strong>把 <code>efinance</code> 變成一個更適合人閱讀、腳本呼叫與重複利用的行情命令列工具</strong></p>
  <p>用一套統一命令樹完成證券搜尋、行情 ID 解析、即時行情查看、歷史行情查詢、資料匯出，以及指標資訊更豐富的 <code>observation</code> 結構化輸出。</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/the-efinance-cli/"><img alt="PyPI 套件" src="https://img.shields.io/badge/PyPI-the--efinance--cli-2563EB"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="上游 efinance" src="https://img.shields.io/badge/Upstream-efinance-B45309"></a>
    <img alt="預設視圖 observation" src="https://img.shields.io/badge/Default%20View-observation-0F766E">
    <img alt="指標增強" src="https://img.shields.io/badge/Indicators-basic%20%7C%20advanced%20%7C%20full-7C3AED">
  </p>
  <p>
    <a href="#installation">安裝</a> ·
    <a href="#thirty-second-start">30 秒上手</a> ·
    <a href="#command-map">命令地圖</a> ·
    <a href="#output-model">輸出模型</a> ·
    <a href="#indicator-coverage">指標覆蓋</a> ·
    <a href="#observation-examples">Observation 範例</a>
  </p>
</div>

<p align="center"><strong><a href="../README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | 繁體中文</strong></p>

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>更容易發現</strong><br />
      相比直接翻閱上游函式，按任務組織的命令樹更容易找到正確入口。
    </td>
    <td width="33%" valign="top">
      <strong>更容易閱讀</strong><br />
      CLI 在 <code>table</code>、<code>json</code>、<code>csv</code>、<code>tsv</code> 之間保持統一輸出體驗，並預設使用 <code>observation</code> 視圖。
    </td>
    <td width="33%" valign="top">
      <strong>指標更豐富</strong><br />
      相容命令可接入大範圍內建技術指標，適合篩選、複盤與後續分析。
    </td>
  </tr>
</table>

<a id="installation"></a>
## 安裝

安裝已發佈到 PyPI 的 `the-efinance-cli`。安裝後可使用 `efinance` 和 `efi` 兩個命令。

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

執行環境要求為 Python `3.10+`。

<a id="what-this-tool-is"></a>
## 這個工具是什麼

> `efinance-cli` 不是一組零散腳本，而是建立在 `efinance` 之上的命令列產品層。

它把上游能力重新整理成一個更適合終端瀏覽、更適合腳本自動化、也更適合結構化消費的公開命令樹。目標不是取代上游行情庫，而是把原有能力變成一個更穩定、更好用的 CLI。

<a id="thirty-second-start"></a>
## 30 秒上手

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>1. 先搜尋</strong>
      <pre lang="bash"><code>efinance search --query AAPL --market US_stock --result-count 5 --format json</code></pre>
      當你只知道代碼、關鍵字或公司名時，最穩妥的入口就是先搜尋。
    </td>
    <td width="33%" valign="top">
      <strong>2. 解析 <code>quote_id</code></strong>
      <pre lang="bash"><code>efinance resolve quote-id --symbol AAPL --market us_stock --format json</code></pre>
      常見美股會被解析成類似 <code>105.AAPL</code> 這樣的統一行情標識。
    </td>
    <td width="33%" valign="top">
      <strong>3. 查詢行情</strong>
      <pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format json</code></pre>
      後續可以繼續進入歷史行情、最新行情、循環刷新與匯出流程。
    </td>
  </tr>
</table>

<a id="main-functions"></a>
## 主要功能

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>標的發現</strong>
      <ul>
        <li>按關鍵字搜尋證券。</li>
        <li>把 symbol 解析成 <code>quote_id</code>。</li>
        <li>從發現階段無縫進入行情與歷史查詢，不需要切換工具。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>跨資產資料存取</strong>
      <ul>
        <li>查詢股票、基金、債券、期貨以及市場級即時資料。</li>
        <li>同時覆蓋最新行情與歷史序列。</li>
        <li>用統一的 watch 模型執行循環刷新。</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>結構化輸出</strong>
      <ul>
        <li>支援匯出為 <code>table</code>、<code>json</code>、<code>csv</code>、<code>tsv</code>。</li>
        <li>預設使用面向公眾閱讀的 <code>observation</code> 視圖。</li>
        <li>當下游程式需要原始結構時，可回退到 <code>raw</code>。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>指標增強</strong>
      <ul>
        <li>支援 <code>basic</code>、<code>advanced</code>、<code>full</code> 三檔。</li>
        <li>覆蓋趨勢、動量、波動率、成交量與價格結構指標。</li>
        <li>為複盤、篩選與自動化流程提供更豐富的市場上下文。</li>
      </ul>
    </td>
  </tr>
</table>

<a id="command-map"></a>
## 命令地圖

<table>
  <thead>
    <tr>
      <th align="left">頂層命令</th>
      <th align="left">職責</th>
      <th align="left">典型用途</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>search</code></td>
      <td>按關鍵字發現標的。</td>
      <td>在還不知道精確標識時先找候選項。</td>
    </tr>
    <tr>
      <td><code>resolve</code></td>
      <td>解析行情標識。</td>
      <td>把 symbol 轉成可重複利用的 <code>quote_id</code>。</td>
    </tr>
    <tr>
      <td><code>quote</code></td>
      <td>跨資產統一行情入口。</td>
      <td>適合已經拿到 <code>quote_id</code> 的場景。</td>
    </tr>
    <tr>
      <td><code>market</code></td>
      <td>市場級查詢。</td>
      <td>做即時掃描和市場映射類查詢。</td>
    </tr>
    <tr>
      <td><code>stock</code></td>
      <td>股票相關查詢。</td>
      <td>歷史、快照、即時列表、資金流、股東與資料。</td>
    </tr>
    <tr>
      <td><code>fund</code></td>
      <td>基金相關查詢。</td>
      <td>淨值歷史、即時估算、配置、管理人與報告。</td>
    </tr>
    <tr>
      <td><code>bond</code></td>
      <td>債券相關查詢。</td>
      <td>資料、價格歷史、即時列表、成交與資金流。</td>
    </tr>
    <tr>
      <td><code>futures</code></td>
      <td>期貨相關查詢。</td>
      <td>名錄、歷史、即時行情與成交明細。</td>
    </tr>
    <tr>
      <td><code>watch</code></td>
      <td>刷新包裝器。</td>
      <td>把支援的子命令放到統一輪詢循環裡執行。</td>
    </tr>
  </tbody>
</table>

<a id="output-model"></a>
## 輸出模型

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>當前真實預設值</strong>
      <ul>
        <li><code>--format table</code></li>
        <li><code>--indicator-level advanced</code></li>
        <li><code>--view observation</code></li>
        <li><code>--trace-window 32</code></li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>使用建議</strong>
      <ul>
        <li><code>observation</code> 是預設的公開閱讀視圖。</li>
        <li>如果要拿原始結構，請傳 <code>--view raw</code>。</li>
        <li>對下游程式來說，<code>json</code> 通常是最合適的格式。</li>
        <li><code>full</code> 比 <code>advanced</code> 提供更多指標上下文，但計算也更重。</li>
      </ul>
    </td>
  </tr>
</table>

<table>
  <thead>
    <tr>
      <th align="left">輸出或執行時參數</th>
      <th align="left">用途</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>--format table|json|csv|tsv</code></td>
      <td>選擇終端閱讀格式或匯出友好的結構化格式。</td>
    </tr>
    <tr>
      <td><code>--full</code></td>
      <td>輸出更完整的結果內容。</td>
    </tr>
    <tr>
      <td><code>--transpose</code></td>
      <td>在部分場景下把表格轉置後再輸出，便於終端閱讀。</td>
    </tr>
    <tr>
      <td><code>--no-index</code></td>
      <td>隱藏表格輸出中的列索引。</td>
    </tr>
    <tr>
      <td><code>--limit N</code></td>
      <td>只保留結果前 <code>N</code> 列。</td>
    </tr>
    <tr>
      <td><code>--output PATH</code></td>
      <td>把渲染後的結果寫入檔案。</td>
    </tr>
    <tr>
      <td><code>--encoding utf-8</code></td>
      <td>設定輸出檔案編碼。</td>
    </tr>
    <tr>
      <td><code>--watch --interval --count --clear/--no-clear</code></td>
      <td>讓支援的命令進入循環刷新模式。</td>
    </tr>
  </tbody>
</table>

<a id="indicator-coverage"></a>
## 指標覆蓋

`efinance-cli` 內建了一套覆蓋面很廣的技術指標集合。相容命令不只會返回原始行情，也能暴露大量指標上下文，因此適合篩選、複盤與後續量化分析。

<details open>
<summary><strong>均線與基礎變換</strong></summary>
<p><code>sma</code> · <code>ema</code> · <code>rma</code> · <code>wma</code> · <code>dema</code> · <code>tema</code> · <code>trima</code> · <code>hma</code> · <code>zlema</code> · <code>highest</code> · <code>lowest</code> · <code>median_price</code> · <code>typical_price</code> · <code>true_range</code></p>
</details>

<details open>
<summary><strong>趨勢與通道類指標</strong></summary>
<p><code>macd</code> · <code>bollinger_bands</code> · <code>donchian_channel</code> · <code>keltner_channel</code> · <code>moving_average_envelope</code> · <code>aroon_indicator</code> · <code>dmi</code> · <code>adx</code> · <code>supertrend</code> · <code>parabolic_sar</code> · <code>ichimoku_cloud</code></p>
</details>

<details open>
<summary><strong>動量類指標</strong></summary>
<p><code>momentum</code> · <code>roc</code> · <code>rsi</code> · <code>stochastic_oscillator</code> · <code>kdj</code> · <code>cci</code> · <code>williams_r</code> · <code>trix</code> · <code>tsi</code> · <code>ultimate_oscillator</code> · <code>dpo</code> · <code>ppo</code></p>
</details>

<details open>
<summary><strong>成交量與資金流類指標</strong></summary>
<p><code>obv</code> · <code>accumulation_distribution</code> · <code>chaikin_money_flow</code> · <code>chaikin_oscillator</code> · <code>mfi</code> · <code>vwap</code> · <code>force_index</code> · <code>ease_of_movement</code> · <code>price_volume_trend</code> · <code>volume_ratio</code></p>
</details>

<details open>
<summary><strong>波動率類指標</strong></summary>
<p><code>atr</code> · <code>natr</code> · <code>historical_volatility</code> · <code>chaikin_volatility</code> · <code>mass_index</code></p>
</details>

<details open>
<summary><strong>價格結構類指標</strong></summary>
<p><code>pivot_points</code> · <code>fibonacci_retracement</code> · <code>rolling_support_resistance</code></p>
</details>

<details open>
<summary><strong>常見中文技術分析指標</strong></summary>
<p><code>bias</code> · <code>bbi</code> · <code>psy</code> · <code>vr</code> · <code>mtm</code> · <code>dma</code> · <code>brar</code> · <code>cr</code> · <code>emv</code> · <code>asi</code></p>
</details>

<table>
  <thead>
    <tr>
      <th align="left">等級</th>
      <th align="left">實際能得到什麼</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>basic</code></td>
      <td>提供 MA、EMA、MACD、RSI、KDJ、BOLL、ATR、OBV 等核心趨勢與動量指標。</td>
    </tr>
    <tr>
      <td><code>advanced</code></td>
      <td>進一步覆蓋 ADX、Donchian、Keltner、SuperTrend、MFI、PVT、CMF、VWAP、VR、PSY 等趨勢強度、通道與資金流指標。</td>
    </tr>
    <tr>
      <td><code>full</code></td>
      <td>繼續加入 Ichimoku、SAR、Mass Index、Pivot Points、Fibonacci Retracement、support/resistance、ADL、Chaikin Oscillator、Chaikin Volatility、EMV 等更重的結構層指標。</td>
    </tr>
  </tbody>
</table>

<a id="observation-examples"></a>
## Observation 範例

下面的範例只展示公開閱讀用的 `observation` 格式。

<details open>
<summary><strong>最新行情 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance quote price latest --quote-ids 105.AAPL --format table --indicator-level full --trace-window 4</code></pre>

<p><strong>典型輸出</strong></p>

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
<summary><strong>歷史行情 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format table --indicator-level advanced --trace-window 4</code></pre>

<p><strong>典型輸出</strong></p>

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
<summary><strong>多標的基金 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format table --view observation --trace-window 4</code></pre>

<p><strong>典型輸出</strong></p>

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
## 常見使用方式

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>搜尋並查看</strong>
      <pre lang="bash"><code>efinance search --query NVDA --market US_stock
efinance resolve quote-id --symbol NVDA --market us_stock
efinance quote price latest --quote-ids 105.NVDA</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>循環觀察單個行情</strong>
      <pre lang="bash"><code>efinance watch --interval 5 --count 3 quote price latest --quote-ids 105.AAPL --format json</code></pre>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>批量基金淨值歷史</strong>
      <pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format json</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>市場級即時掃描</strong>
      <pre lang="bash"><code>efinance market price live --market m:105+t:3 --format json</code></pre>
    </td>
  </tr>
</table>

<a id="notes"></a>
## 說明

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>資料源邊界</strong>
      <ul>
        <li>CLI 的可用性依賴上游行情資料源。</li>
        <li>即時行情穩定性受網路狀態和源站行為影響。</li>
        <li>不同命令支援的指標增強深度並不完全相同。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>使用邊界</strong>
      <ul>
        <li>帶副作用的命令，例如報告下載，應有意識地單獨使用。</li>
        <li>如果結果要交給別的程式消費，優先使用 <code>json</code>。</li>
        <li>如果人或 agent 更需要簡潔市場上下文而不是原始表格，優先使用 <code>observation</code>。</li>
      </ul>
    </td>
  </tr>
</table>

<a id="license"></a>
## 授權

See [../LICENSE](../LICENSE).
