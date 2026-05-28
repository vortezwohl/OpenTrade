<div align="center">
  <h1>efinance-cli</h1>
  <p><strong>把 <code>efinance</code> 变成一个更适合人阅读、脚本调用与复用的行情命令行工具</strong></p>
  <p>用一套统一命令树完成证券搜索、行情 ID 解析、实时行情查看、历史行情查询、数据导出，以及指标信息丰富的 <code>observation</code> 结构化输出。</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/the-efinance-cli/"><img alt="PyPI 包" src="https://img.shields.io/badge/PyPI-the--efinance--cli-2563EB"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="上游 efinance" src="https://img.shields.io/badge/Upstream-efinance-B45309"></a>
    <img alt="默认视图 observation" src="https://img.shields.io/badge/Default%20View-observation-0F766E">
    <img alt="指标增强" src="https://img.shields.io/badge/Indicators-basic%20%7C%20advanced%20%7C%20full-7C3AED">
  </p>
  <p>
    <a href="#installation">安装</a> ·
    <a href="#thirty-second-start">30 秒上手</a> ·
    <a href="#command-map">命令地图</a> ·
    <a href="#output-model">输出模型</a> ·
    <a href="#indicator-coverage">指标覆盖</a> ·
    <a href="#observation-examples">Observation 示例</a>
  </p>
</div>

<p align="center"><strong><a href="../README.md">English</a> | 简体中文 | <a href="README.zh-TW.md">繁體中文</a></strong></p>

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>更易发现</strong><br />
      相比直接翻上游函数，按任务组织的命令树更容易找到正确入口。
    </td>
    <td width="33%" valign="top">
      <strong>更易阅读</strong><br />
      CLI 在 <code>table</code>、<code>json</code>、<code>csv</code>、<code>tsv</code> 之间保持统一输出体验，并默认使用 <code>observation</code> 视图。
    </td>
    <td width="33%" valign="top">
      <strong>指标更丰富</strong><br />
      兼容命令可接入大范围内置技术指标，适合筛选、复盘和后续分析。
    </td>
  </tr>
</table>

<a id="installation"></a>
## 安装

安装已发布到 PyPI 的 `the-efinance-cli`。安装后可使用 `efinance` 和 `efi` 两个命令。

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

运行环境要求为 Python `3.10+`。

<a id="what-this-tool-is"></a>
## 这个工具是什么

> `efinance-cli` 不是一组零散脚本，而是构建在 `efinance` 之上的命令行产品层。

它把上游能力重新整理成一个更适合终端浏览、更适合脚本自动化、也更适合结构化消费的公开命令树。目标不是替代上游行情库，而是把原有能力变成一个更稳定、更好用的 CLI。

<a id="thirty-second-start"></a>
## 30 秒上手

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <strong>1. 先搜索</strong>
      <pre lang="bash"><code>efinance search --query AAPL --market US_stock --result-count 5 --format json</code></pre>
      当你只知道代码、关键字或公司名时，最稳妥的入口就是先搜索。
    </td>
    <td width="33%" valign="top">
      <strong>2. 解析 <code>quote_id</code></strong>
      <pre lang="bash"><code>efinance resolve quote-id --symbol AAPL --market us_stock --format json</code></pre>
      常见美股会被解析成类似 <code>105.AAPL</code> 这样的统一行情标识。
    </td>
    <td width="33%" valign="top">
      <strong>3. 查询行情</strong>
      <pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format json</code></pre>
      后续可以继续进入历史行情、最新行情、循环刷新和导出流程。
    </td>
  </tr>
</table>

<a id="main-functions"></a>
## 主要功能

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>标的发现</strong>
      <ul>
        <li>按关键字搜索证券。</li>
        <li>把 symbol 解析成 <code>quote_id</code>。</li>
        <li>从发现阶段无缝进入行情与历史查询，不需要切换工具。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>跨资产数据访问</strong>
      <ul>
        <li>查询股票、基金、债券、期货以及市场级实时数据。</li>
        <li>同时覆盖最新行情与历史序列。</li>
        <li>用统一的 watch 模型执行循环刷新。</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>结构化输出</strong>
      <ul>
        <li>支持导出为 <code>table</code>、<code>json</code>、<code>csv</code>、<code>tsv</code>。</li>
        <li>默认使用面向公众阅读的 <code>observation</code> 视图。</li>
        <li>当下游程序需要原始结构时，可回退到 <code>raw</code>。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>指标增强</strong>
      <ul>
        <li>支持 <code>basic</code>、<code>advanced</code>、<code>full</code> 三档。</li>
        <li>覆盖趋势、动量、波动率、成交量和价格结构指标。</li>
        <li>为复盘、筛选和自动化流程提供更丰富的市场上下文。</li>
      </ul>
    </td>
  </tr>
</table>

<a id="command-map"></a>
## 命令地图

<table>
  <thead>
    <tr>
      <th align="left">顶层命令</th>
      <th align="left">职责</th>
      <th align="left">典型用途</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>search</code></td>
      <td>按关键字发现标的。</td>
      <td>在还不知道精确标识时先找候选项。</td>
    </tr>
    <tr>
      <td><code>resolve</code></td>
      <td>解析行情标识。</td>
      <td>把 symbol 转成可复用的 <code>quote_id</code>。</td>
    </tr>
    <tr>
      <td><code>quote</code></td>
      <td>跨资产统一行情入口。</td>
      <td>适合已经拿到 <code>quote_id</code> 的场景。</td>
    </tr>
    <tr>
      <td><code>market</code></td>
      <td>市场级查询。</td>
      <td>做实时扫描和市场映射类查询。</td>
    </tr>
    <tr>
      <td><code>stock</code></td>
      <td>股票相关查询。</td>
      <td>历史、快照、实时列表、资金流、股东和资料。</td>
    </tr>
    <tr>
      <td><code>fund</code></td>
      <td>基金相关查询。</td>
      <td>净值历史、实时估算、配置、管理人和报告。</td>
    </tr>
    <tr>
      <td><code>bond</code></td>
      <td>债券相关查询。</td>
      <td>资料、价格历史、实时列表、成交和资金流。</td>
    </tr>
    <tr>
      <td><code>futures</code></td>
      <td>期货相关查询。</td>
      <td>名录、历史、实时行情和成交明细。</td>
    </tr>
    <tr>
      <td><code>watch</code></td>
      <td>刷新包装器。</td>
      <td>把支持的子命令放到统一轮询循环里执行。</td>
    </tr>
  </tbody>
</table>

<a id="output-model"></a>
## 输出模型

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>当前真实默认值</strong>
      <ul>
        <li><code>--format table</code></li>
        <li><code>--indicator-level advanced</code></li>
        <li><code>--view observation</code></li>
        <li><code>--trace-window 32</code></li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>使用建议</strong>
      <ul>
        <li><code>observation</code> 是默认的公开阅读视图。</li>
        <li>如果要拿原始结构，请传 <code>--view raw</code>。</li>
        <li>对下游程序来说，<code>json</code> 通常是最合适的格式。</li>
        <li><code>full</code> 比 <code>advanced</code> 提供更多指标上下文，但计算也更重。</li>
      </ul>
    </td>
  </tr>
</table>

<table>
  <thead>
    <tr>
      <th align="left">输出或运行时参数</th>
      <th align="left">用途</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>--format table|json|csv|tsv</code></td>
      <td>选择终端阅读格式或导出友好的结构化格式。</td>
    </tr>
    <tr>
      <td><code>--full</code></td>
      <td>输出更完整的结果内容。</td>
    </tr>
    <tr>
      <td><code>--transpose</code></td>
      <td>在部分场景下把表格转置后再输出，便于终端阅读。</td>
    </tr>
    <tr>
      <td><code>--no-index</code></td>
      <td>隐藏表格输出中的行索引。</td>
    </tr>
    <tr>
      <td><code>--limit N</code></td>
      <td>只保留结果前 <code>N</code> 行。</td>
    </tr>
    <tr>
      <td><code>--output PATH</code></td>
      <td>把渲染后的结果写入文件。</td>
    </tr>
    <tr>
      <td><code>--encoding utf-8</code></td>
      <td>设置输出文件编码。</td>
    </tr>
    <tr>
      <td><code>--watch --interval --count --clear/--no-clear</code></td>
      <td>让支持的命令进入循环刷新模式。</td>
    </tr>
  </tbody>
</table>

<a id="indicator-coverage"></a>
## 指标覆盖

`efinance-cli` 内置了一套覆盖面很广的技术指标集合。兼容命令不仅能返回原始行情，也能暴露大量指标上下文，因此适合筛选、复盘与后续量化分析。

<details open>
<summary><strong>均线与基础变换</strong></summary>
<p><code>sma</code> · <code>ema</code> · <code>rma</code> · <code>wma</code> · <code>dema</code> · <code>tema</code> · <code>trima</code> · <code>hma</code> · <code>zlema</code> · <code>highest</code> · <code>lowest</code> · <code>median_price</code> · <code>typical_price</code> · <code>true_range</code></p>
</details>

<details open>
<summary><strong>趋势与通道类指标</strong></summary>
<p><code>macd</code> · <code>bollinger_bands</code> · <code>donchian_channel</code> · <code>keltner_channel</code> · <code>moving_average_envelope</code> · <code>aroon_indicator</code> · <code>dmi</code> · <code>adx</code> · <code>supertrend</code> · <code>parabolic_sar</code> · <code>ichimoku_cloud</code></p>
</details>

<details open>
<summary><strong>动量类指标</strong></summary>
<p><code>momentum</code> · <code>roc</code> · <code>rsi</code> · <code>stochastic_oscillator</code> · <code>kdj</code> · <code>cci</code> · <code>williams_r</code> · <code>trix</code> · <code>tsi</code> · <code>ultimate_oscillator</code> · <code>dpo</code> · <code>ppo</code></p>
</details>

<details open>
<summary><strong>成交量与资金流类指标</strong></summary>
<p><code>obv</code> · <code>accumulation_distribution</code> · <code>chaikin_money_flow</code> · <code>chaikin_oscillator</code> · <code>mfi</code> · <code>vwap</code> · <code>force_index</code> · <code>ease_of_movement</code> · <code>price_volume_trend</code> · <code>volume_ratio</code></p>
</details>

<details open>
<summary><strong>波动率类指标</strong></summary>
<p><code>atr</code> · <code>natr</code> · <code>historical_volatility</code> · <code>chaikin_volatility</code> · <code>mass_index</code></p>
</details>

<details open>
<summary><strong>价格结构类指标</strong></summary>
<p><code>pivot_points</code> · <code>fibonacci_retracement</code> · <code>rolling_support_resistance</code></p>
</details>

<details open>
<summary><strong>常见中文技术分析指标</strong></summary>
<p><code>bias</code> · <code>bbi</code> · <code>psy</code> · <code>vr</code> · <code>mtm</code> · <code>dma</code> · <code>brar</code> · <code>cr</code> · <code>emv</code> · <code>asi</code></p>
</details>

<table>
  <thead>
    <tr>
      <th align="left">等级</th>
      <th align="left">实际能得到什么</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>basic</code></td>
      <td>提供 MA、EMA、MACD、RSI、KDJ、BOLL、ATR、OBV 等核心趋势与动量指标。</td>
    </tr>
    <tr>
      <td><code>advanced</code></td>
      <td>进一步覆盖 ADX、Donchian、Keltner、SuperTrend、MFI、PVT、CMF、VWAP、VR、PSY 等趋势强度、通道与资金流指标。</td>
    </tr>
    <tr>
      <td><code>full</code></td>
      <td>继续加入 Ichimoku、SAR、Mass Index、Pivot Points、Fibonacci Retracement、support/resistance、ADL、Chaikin Oscillator、Chaikin Volatility、EMV 等更重的结构层指标。</td>
    </tr>
  </tbody>
</table>

<a id="observation-examples"></a>
## Observation 示例

下面的示例只展示公开阅读用的 `observation` 格式。

<details open>
<summary><strong>最新行情 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance quote price latest --quote-ids 105.AAPL --format table --indicator-level full --trace-window 4</code></pre>

<p><strong>典型输出</strong></p>

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
<summary><strong>历史行情 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format table --indicator-level advanced --trace-window 4</code></pre>

<p><strong>典型输出</strong></p>

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
<summary><strong>多标的基金 observation</strong></summary>

<p><strong>命令</strong></p>
<pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format table --view observation --trace-window 4</code></pre>

<p><strong>典型输出</strong></p>

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
## 常见使用方式

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>搜索并查看</strong>
      <pre lang="bash"><code>efinance search --query NVDA --market US_stock
efinance resolve quote-id --symbol NVDA --market us_stock
efinance quote price latest --quote-ids 105.NVDA</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>循环观察单个行情</strong>
      <pre lang="bash"><code>efinance watch --interval 5 --count 3 quote price latest --quote-ids 105.AAPL --format json</code></pre>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>批量基金净值历史</strong>
      <pre lang="bash"><code>efinance fund nav history-batch --symbols 161725 --symbols 005827 --format json</code></pre>
    </td>
    <td width="50%" valign="top">
      <strong>市场级实时扫描</strong>
      <pre lang="bash"><code>efinance market price live --market m:105+t:3 --format json</code></pre>
    </td>
  </tr>
</table>

<a id="notes"></a>
## 说明

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <strong>数据源边界</strong>
      <ul>
        <li>CLI 的可用性依赖上游行情数据源。</li>
        <li>实时行情稳定性受网络状态和源站行为影响。</li>
        <li>不同命令支持的指标增强深度并不完全相同。</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <strong>使用边界</strong>
      <ul>
        <li>带副作用的命令，例如报告下载，应有意识地单独使用。</li>
        <li>如果结果要交给别的程序消费，优先使用 <code>json</code>。</li>
        <li>如果人或 agent 更需要简洁市场上下文而不是原始表格，优先使用 <code>observation</code>。</li>
      </ul>
    </td>
  </tr>
</table>

<a id="license"></a>
## 许可证

See [../LICENSE](../LICENSE).
