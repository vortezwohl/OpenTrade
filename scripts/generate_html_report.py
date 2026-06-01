#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""根据 raw JSON 测试结果生成 HTML 报告。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_JSON = PROJECT_ROOT / "docs" / "20260601-raw-results.json"
OUTPUT_HTML = PROJECT_ROOT / "docs" / "20260601-测试结论.html"


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_result_section(result: dict, idx: int) -> str:
    """渲染单条测试结果。"""
    status_class = "ok" if result["success"] else ("warn" if result.get("allow_failure") else "danger")
    status_text = "PASS" if result["success"] else ("FAIL*" if result.get("allow_failure") else "FAIL")
    if result["exit_code"] == -1:
        status_text = "TIMEOUT"
        status_class = "warn"

    rows = []
    rows.append(f'<div class="test-case" id="test-{idx}">')
    rows.append(f'<div class="test-header {status_class}">')
    rows.append(f'<span class="test-id">#{idx}</span>')
    rows.append(f'<span class="test-cmd">efinance {escape_html(result["command"])}</span>')
    rows.append(f'<span class="test-status badge-{status_class}">{status_text}</span>')
    rows.append(f'<span class="test-time">{result["elapsed_ms"]}ms</span>')
    rows.append(f'<span class="test-backend">{result["backend"]}/{result["format"]}</span>')
    rows.append('</div>')

    # 备注
    if result.get("note"):
        rows.append(f'<div class="test-note">{escape_html(result["note"])}</div>')

    # 错误
    if result.get("error"):
        rows.append(f'<div class="test-error">{escape_html(result["error"])}</div>')

    # stderr
    if result.get("stderr"):
        stderr_text = result["stderr"][:5000]
        rows.append('<details class="test-stderr"><summary>stderr</summary>')
        rows.append(f'<pre>{escape_html(stderr_text)}</pre>')
        rows.append('</details>')

    # stdout (最重要的部分 - 真实的CLI输出)
    if result.get("stdout"):
        stdout_text = result["stdout"]
        rows.append('<details class="test-stdout" open><summary>真实 CLI 输出</summary>')
        rows.append(f'<pre>{escape_html(stdout_text)}</pre>')
        rows.append('</details>')

    rows.append('</div>')
    return "\n".join(rows)


def main() -> None:
    data = json.loads(RAW_JSON.read_text(encoding="utf-8"))
    summary = data["summary"]
    results = data["results"]

    # ---- 统计 ----
    cat_stats = summary.get("category_stats", {})
    cat_rows = []
    for cat, stats in sorted(cat_stats.items()):
        rate = round(stats["passed"] / max(stats["total"], 1) * 100, 1)
        cat_rows.append(f"""
        <tr>
          <td>{cat}</td>
          <td>{stats['total']}</td>
          <td>{stats['passed']}</td>
          <td>{stats['failed']}</td>
          <td>{rate}%</td>
        </tr>""")

    # ---- 生成 HTML ----
    html_parts = []
    
    # 头部
    html_parts.append(f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>efinance-cli 全量真实 API 回归测试 · 2026-06-01</title>
<style>
:root {{
  --bg: #f3f7fa;
  --panel: rgba(255,255,255,0.92);
  --panel-strong: #eef4f8;
  --text: #18212b;
  --muted: #445260;
  --line: rgba(71,96,120,0.22);
  --accent: #2e6f97;
  --accent-soft: rgba(46,111,151,0.12);
  --ok: #1f6f54;
  --ok-bg: #e6f4ec;
  --warn: #8f5a16;
  --warn-bg: #fef3e2;
  --danger: #8a2f33;
  --danger-bg: #fce8e8;
  --code-bg: #e8f0f5;
  --code-strong-bg: #182531;
  --code-strong-text: #edf8ff;
  --shadow: 0 22px 70px rgba(27,48,66,0.1);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; color: var(--text);
  background: radial-gradient(circle at top right, rgba(46,111,151,0.16), transparent 24%),
              linear-gradient(180deg, #edf4f8 0%, var(--bg) 100%);
  font-family: "Georgia", "Times New Roman", "Noto Serif SC", serif;
  line-height: 1.86;
}}
code, pre {{ font-family: "Cascadia Code", "Consolas", monospace; }}
pre {{
  margin: 0.5rem 0 0; padding: 0.8rem 1rem;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
  font-size: 0.82rem; line-height: 1.5;
  border: 1px solid var(--line); border-radius: 6px;
  background: var(--code-strong-bg); color: var(--code-strong-text);
}}
.essay {{ max-width: 1200px; margin: 0 auto; padding: 32px 18px 64px; }}
.hero {{ margin-bottom: 2rem; }}
.hero h1 {{ font-size: 2rem; color: var(--accent); margin: 0 0 0.3rem; }}
.hero .meta {{ color: var(--muted); font-size: 0.92rem; }}
.summary-cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.5rem 0; }}
.summary-card {{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 1rem 1.4rem; min-width: 140px; text-align: center;
}}
.summary-card .num {{ font-size: 2rem; font-weight: bold; }}
.summary-card .label {{ color: var(--muted); font-size: 0.85rem; }}
.num-ok {{ color: var(--ok); }}
.num-danger {{ color: var(--danger); }}
.num-warn {{ color: var(--warn); }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ padding: 0.5rem 0.8rem; text-align: left; border-bottom: 1px solid var(--line); }}
th {{ background: var(--panel-strong); font-weight: 600; }}
.test-case {{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 8px; margin: 0.6rem 0; overflow: hidden;
}}
.test-header {{
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.5rem 0.8rem; font-size: 0.88rem;
}}
.test-header.ok {{ background: var(--ok-bg); border-left: 4px solid var(--ok); }}
.test-header.warn {{ background: var(--warn-bg); border-left: 4px solid var(--warn); }}
.test-header.danger {{ background: var(--danger-bg); border-left: 4px solid var(--danger); }}
.test-id {{ font-weight: bold; color: var(--muted); min-width: 2rem; }}
.test-cmd {{ font-family: monospace; flex: 1; }}
.test-status {{ font-weight: bold; font-size: 0.78rem; }}
.test-time {{ color: var(--muted); font-size: 0.8rem; }}
.test-backend {{ color: var(--accent); font-size: 0.78rem; }}
.badge-ok {{ color: var(--ok); }}
.badge-danger {{ color: var(--danger); }}
.badge-warn {{ color: var(--warn); }}
.test-note {{ padding: 0.2rem 0.8rem; color: var(--muted); font-size: 0.82rem; }}
.test-error {{ padding: 0.2rem 0.8rem; color: var(--danger); font-size: 0.82rem; }}
.test-stderr, .test-stdout {{ padding: 0 0.8rem 0.5rem; }}
.test-stderr summary, .test-stdout summary {{
  cursor: pointer; color: var(--accent); font-size: 0.85rem; padding: 0.3rem 0;
}}
.section {{ margin: 2rem 0; }}
.section h2 {{ color: var(--accent); border-bottom: 2px solid var(--accent-soft); padding-bottom: 0.3rem; }}
.nav {{ position: sticky; top: 0; background: var(--panel); border-bottom: 1px solid var(--line); padding: 0.5rem 1rem; z-index: 10; display: flex; gap: 0.8rem; flex-wrap: wrap; font-size: 0.85rem; }}
.nav a {{ color: var(--accent); text-decoration: none; }}
.nav a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="nav">
  <a href="#summary">概述</a>
  <a href="#category">分类统计</a>
  <a href="#results">详细结果</a>
</div>
<div class="essay">
<div class="hero">
  <h1>efinance-cli 全量真实 API 回归测试</h1>
  <div class="meta">
    测试时间: {summary.get("test_time", "")} ~ {summary.get("end_time", "")}<br>
    总耗时: {summary.get("duration_seconds", 0):.0f} 秒
  </div>
</div>

<div class="section" id="summary">
<h2>测试概述</h2>
<div class="summary-cards">
  <div class="summary-card">
    <div class="num">{summary["total"]}</div>
    <div class="label">总用例</div>
  </div>
  <div class="summary-card">
    <div class="num num-ok">{summary["passed"]}</div>
    <div class="label">通过</div>
  </div>
  <div class="summary-card">
    <div class="num num-danger">{summary["failed"]}</div>
    <div class="label">失败</div>
  </div>
  <div class="summary-card">
    <div class="num num-warn">{summary["timeout"]}</div>
    <div class="label">超时</div>
  </div>
  <div class="summary-card">
    <div class="num">{summary["pass_rate"]}%</div>
    <div class="label">通过率</div>
  </div>
</div>
<p>
  本报告为 <strong>efinance-cli v0.2.0</strong> 的全量真实 API 调用回归测试。<br>
  每条命令均通过真实网络请求调用 efinance / akshare / yfinance 后端，
  不做 mock，记录完整的标准输出、错误信息与耗时。<br>
  测试环境: Python 3.10, Windows, Asia/Shanghai 时区。
</p>
</div>

<div class="section" id="category">
<h2>分类统计</h2>
<table>
<tr><th>分类</th><th>总数</th><th>通过</th><th>失败</th><th>通过率</th></tr>
{"".join(cat_rows)}
</table>
</div>

<div class="section" id="results">
<h2>详细结果 (共 {len(results)} 条)</h2>
<p style="color:var(--muted)">点击每个测试项的「真实 CLI 输出」展开查看完整输出。PASS=通过, FAIL=失败, FAIL*=允许失败, TIMEOUT=超时(90s)</p>
''')

    # 渲染每条结果
    for i, result in enumerate(results, 1):
        html_parts.append(render_result_section(result, i))

    html_parts.append('''
</div>
</div>
</body>
</html>''')

    html_content = "\n".join(html_parts)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"HTML 报告已生成: {OUTPUT_HTML}")
    print(f"大小: {len(html_content)} 字符")


if __name__ == "__main__":
    main()
