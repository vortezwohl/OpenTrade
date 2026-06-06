<div align="center">
  <h1>OpenTrade</h1>
  <p><strong>終端裡的市場資料，專為人與 Agent 而設計。</strong></p>
  <p>用一套統一命令樹完成證券搜尋、行情查看、歷史行情查詢、資料匯出，以及指標資訊更豐富的 <code>observation</code> 結構化輸出。</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/opentrade/"><img alt="PyPI 套件" src="https://img.shields.io/badge/PyPI-opentrade-2563EB"></a>
    <a href="https://pypi.org/project/akshare/"><img alt="後端 akshare" src="https://img.shields.io/badge/Backend-akshare-1D4ED8"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="後端 efinance" src="https://img.shields.io/badge/Backend-efinance-B45309"></a>
    <a href="https://pypi.org/project/yfinance/"><img alt="後端 yfinance" src="https://img.shields.io/badge/Backend-yfinance-15803D"></a>
  </p>
  <p>
    <a href="#installation">安裝</a> ·
    <a href="#agent-skills">Agent Skills</a> ·
    <a href="#quick-start">快速開始</a> ·
    <a href="#command-tree">命令樹</a> ·
    <a href="#output-and-defaults">輸出與預設值</a> ·
    <a href="#indicator-support">技術指標支援</a> ·
    <a href="#more-docs">更多文件</a>
  </p>
</div>

<p align="center"><strong><a href="../README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | 繁體中文</strong></p>

## 安裝

安裝已發佈到 PyPI 的 `opentrade`。安裝後可使用 `opentrade` 和 `optr` 兩個命令。

```bash
uv add -U opentrade
opentrade --help
```

```bash
pip install -U opentrade
opentrade --help
```

執行環境要求為 Python `3.10+`。

## Agent Skills

OpenTrade 也提供面向 Codex、Claude Code 與其他 Agent 的 skill，用於自動投研工作流。

當你希望 Agent 幫你安裝這些 skill 時，只需要直接說：

> Please install skills from `https://github.com/vortezwohl/OpenTrade`, and place them in my global user skill directory.

這些 skill 主要用於股票、基金、債券、期貨與更廣義市場場景下的自動化投研分析。

## 快速開始

### 1. 搜尋

```bash
opentrade search --query AAPL --market US_stock --result-count 5 --format json
```

當你只知道代碼、關鍵字或公司名時，先搜尋最穩妥。

### 2. 最新行情

```bash
opentrade quote price latest --symbols AAPL --format json
```

當你希望使用跨後端共享 symbol / ticker 流程時，優先使用共享 `quote` 命令。

### 3. 歷史行情

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

需要 K 線、回補、指標或匯出時，進入歷史命令。

## 命令樹

| 命令 | 角色 | 典型用途 |
|---|---|---|
| `search` | 關鍵字搜尋 | 在還不知道精確標識時先找候選標的 |
| `resolve` | 標識解析 | 在需要時把 symbol 解析成 provider 專屬 quote ID |
| `quote` | 跨資產共享查詢 | 統一存取共享 latest、history、profile |
| `stock` | 股票專項流程 | 行情、快照、資金流、股東、資料 |
| `fund` | 基金專項流程 | 淨值、估值、配置、經理、報告 |
| `bond` | 債券專項流程 | 行情、資料、成交、資金流 |
| `futures` | 期貨專項流程 | 目錄、歷史、即時、成交 |
| `market` | 市場級查詢 | 即時掃描與市場映射類查詢 |
| `watch` | 刷新包裝器 | 按固定間隔重複執行支援的命令 |

## 輸出與預設值

當前共享命令的真實預設值：

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`
- 省略 `--backend` 時會解析為 `auto`

實用說明：

- `observation` 是預設的公共輸出視圖。
- 需要未包裝結構時使用 `--view raw`。
- 對腳本和 Agent 來說，`json` 通常最合適。
- `full` 比 `advanced` 提供更豐富的指標上下文，但會消耗更多歷史回補與計算成本。

## 技術指標支援

技術指標增強是 `opentrade` 的核心能力之一，相容命令可以輸出比原始行情更豐富的市場上下文。

| 等級 | 實際會得到什麼 |
|---|---|
| `basic` | 核心趨勢與動量指標，如 MA、EMA、MACD、RSI、KDJ、BOLL、ATR、OBV |
| `advanced` | 更廣的趨勢強度、通道與資金流指標，如 ADX、Donchian、Keltner、SuperTrend、MFI、PVT、CMF、VWAP、VR、PSY |
| `full` | 更完整的結構與市場上下文指標，如 Ichimoku、SAR、Mass Index、Pivot Points、Fibonacci Retracement、支撐阻力、Chaikin Oscillator、Chaikin Volatility、EMV |

代表性的指標家族包括：

- 均線與基礎變換
- 趨勢與通道指標
- 動量指標
- 成交量與資金流指標
- 波動率指標
- 價格結構指標
- 常見中文技術指標

完整列表和分組請見 [docs/indicator-coverage.md](../docs/indicator-coverage.md)。

## 後端說明

- shared 命令預設走 `auto`，當前一個 backend 失敗時，`auto` 可能回退到其他 backend。
- shared `symbols` 不是東方財富 `quote_id`。
- `yfinance` 的分時歷史視窗限制較嚴格，並且在本專案裡更偏向單標的語義。
- 某條命令即使在 `auto` 下最終成功，也可能因為所選 backend 的歷史回補失敗而遺失 enriched observation 欄位。

更詳細的 backend 約束與排障說明請見 [docs/backend-notes.md](../docs/backend-notes.md)。

## 常見任務

### 搜尋並查看

```bash
opentrade search --query NVDA --market US_stock
opentrade quote price latest --symbols NVDA
```

### 查看歷史

```bash
opentrade stock price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

### 循環刷新

```bash
opentrade watch --interval 5 --count 3 quote price latest --symbols AAPL --format json
```

### 匯出資料

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format csv --output aapl-history.csv
```

## 更多文件

- [技術指標覆蓋](../docs/indicator-coverage.md)
- [Observation 範例](../docs/observation-examples.md)
- [後端說明](../docs/backend-notes.md)
- [English README](../README.md)
- [简体中文 README](README.zh-CN.md)

## 授權

MIT License。
