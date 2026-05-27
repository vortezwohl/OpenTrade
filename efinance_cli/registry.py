"""efinance 模块与命令的注册中心。

这里采用轻量的 Facade 思路：命令层不直接散落依赖第三方模块，而是统一从注册中心
拿到模块对象和函数元数据。这样后续若要补别名、过滤不可暴露函数、定制帮助文本，
都可以在此处集中调整。
"""

from __future__ import annotations

import inspect
from typing import Any

import efinance

from efinance_cli.fund_compat import get_base_info as get_fund_base_info_compat
from efinance_cli.models import CommandSpec


MODULE_HELP_TEXT: dict[str, str] = {
    "stock": "股票相关能力，覆盖行情、K 线、龙虎榜、股东信息等。",
    "fund": "基金相关能力，覆盖净值、估算涨跌、持仓分布与报告下载等。",
    "bond": "债券相关能力，覆盖可转债列表、行情、K 线与资金流。",
    "futures": "期货相关能力，覆盖基础信息、实时行情、K 线与成交明细。",
    "common": "通用查询能力，适合直接按底层分类与 quote_id 访问。",
    "utils": "工具能力，覆盖搜索、quote_id 获取与市场扩展辅助。",
}

ALLOWED_FUNCTIONS: dict[str, set[str]] = {
    "stock": {
        "get_all_company_performance",
        "get_all_report_dates",
        "get_base_info",
        "get_belong_board",
        "get_daily_billboard",
        "get_deal_detail",
        "get_history_bill",
        "get_latest_holder_number",
        "get_latest_ipo_info",
        "get_latest_quote",
        "get_members",
        "get_quote_history",
        "get_quote_snapshot",
        "get_realtime_quotes",
        "get_today_bill",
        "get_top10_stock_holder_info",
    },
    "fund": {
        "get_base_info",
        "get_fund_codes",
        "get_fund_manager",
        "get_industry_distribution",
        "get_invest_position",
        "get_pdf_reports",
        "get_period_change",
        "get_public_dates",
        "get_quote_history",
        "get_quote_history_multi",
        "get_realtime_increase_rate",
        "get_types_percentage",
    },
    "bond": {
        "get_all_base_info",
        "get_base_info",
        "get_deal_detail",
        "get_history_bill",
        "get_quote_history",
        "get_realtime_quotes",
        "get_today_bill",
    },
    "futures": {
        "get_deal_detail",
        "get_futures_base_info",
        "get_quote_history",
        "get_realtime_quotes",
    },
    "common": {
        "get_base_info",
        "get_deal_detail",
        "get_history_bill",
        "get_latest_quote",
        "get_quote_history",
        "get_realtime_quotes_by_fs",
        "get_today_bill",
    },
    "utils": {
        "add_market",
        "get_quote_id",
        "search_quote",
        "search_quote_locally",
    },
}

FUNCTION_HELP_OVERRIDES: dict[tuple[str, str], str] = {
    ("fund", "get_pdf_reports"): "下载基金 PDF 报告到指定目录。",
    ("utils", "search_quote"): "根据关键字搜索证券候选项。",
    ("utils", "get_quote_id"): "把证券关键字转换为东方财富行情 ID。",
    ("utils", "add_market"): "向本地 FS 分类映射中追加市场定义。",
}

SIDE_EFFECT_FUNCTIONS: set[tuple[str, str]] = {
    ("fund", "get_pdf_reports"),
    ("utils", "add_market"),
}

WATCH_UNSUPPORTED_FUNCTIONS: set[tuple[str, str]] = {
    ("fund", "get_pdf_reports"),
    ("utils", "add_market"),
}

CALLBACK_OVERRIDES: dict[tuple[str, str], Any] = {
    ("fund", "get_base_info"): get_fund_base_info_compat,
}


def get_module(module_name: str) -> Any:
    """根据模块名获取 efinance 子模块。"""
    try:
        return getattr(efinance, module_name)
    except AttributeError as exc:
        raise KeyError(f"未知模块: {module_name}") from exc


def list_module_names() -> list[str]:
    """返回允许暴露到 CLI 的模块名列表。"""
    return list(MODULE_HELP_TEXT.keys())


def build_command_specs(module_name: str) -> list[CommandSpec]:
    """为指定模块构建命令描述列表。"""
    module = get_module(module_name)
    specs: list[CommandSpec] = []
    allowed = ALLOWED_FUNCTIONS[module_name]
    for name in sorted(item for item in dir(module) if not item.startswith("_")):
        if name not in allowed:
            continue
        obj = getattr(module, name)
        key = (module_name, name)
        callback = CALLBACK_OVERRIDES.get(key, obj)
        inspected_obj = inspect.unwrap(obj)
        if not callable(inspected_obj):
            continue
        module_path = getattr(inspected_obj, "__module__", "")
        if module_name != "utils" and not module_path.startswith(module.__name__):
            continue
        doc = inspect.getdoc(callback) or inspect.getdoc(inspected_obj) or ""
        help_text = FUNCTION_HELP_OVERRIDES.get(key) or doc.splitlines()[0] if doc else f"{module_name}.{name}"
        specs.append(
            CommandSpec(
                module_name=module_name,
                function_name=name,
                callback=callback,
                help_text=help_text,
                allow_watch=key not in WATCH_UNSUPPORTED_FUNCTIONS,
                has_side_effect=key in SIDE_EFFECT_FUNCTIONS,
            )
        )
    return specs


def get_command_spec(module_name: str, function_name: str) -> CommandSpec:
    """获取某个函数对应的命令描述。"""
    for spec in build_command_specs(module_name):
        if spec.function_name == function_name:
            return spec
    raise KeyError(f"未知命令: {module_name}.{function_name}")
