"""efinance 模块与语义化 CLI 命令的注册中心。

这里集中维护三类信息：

1. 哪些上游函数允许暴露给 CLI；
2. 每个函数对应的自然化命令路径；
3. 回调、帮助文本、副作用和 watch 支持等命令元数据。

当前版本不再把“模块名 + 函数名”直接暴露为最终命令路径，而是以用户任务视角组织命令树。
"""

from __future__ import annotations

import inspect
from typing import Any

import efinance

from efinance_cli.fund_compat import get_base_info as get_fund_base_info_compat
from efinance_cli.models import CommandSpec
from efinance_cli.retry_utils import with_network_retry


VISIBLE_ROOT_GROUPS: tuple[str, ...] = (
    "stock",
    "fund",
    "bond",
    "futures",
    "quote",
    "market",
    "resolve",
)

GROUP_HELP_TEXT: dict[str, str] = {
    "stock": "股票相关能力，按价格、资金流、成交、资料和事件类任务组织。",
    "fund": "基金相关能力，按净值、估值、配置、资料和报告类任务组织。",
    "bond": "债券相关能力，按价格、资金流、成交和资料类任务组织。",
    "futures": "期货相关能力，按价格、成交和名录类任务组织。",
    "quote": "高级通用行情入口，适合已知 quote id 或跨品类统一访问场景。",
    "market": "市场级扫描与市场配置能力。",
    "resolve": "把关键字或代码解析为内部行情标识。",
}

SOURCE_MODULES: dict[str, str] = {
    "stock": "stock",
    "fund": "fund",
    "bond": "bond",
    "futures": "futures",
    "quote": "common",
    "market": "common",
    "resolve": "utils",
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

CLI_PATH_OVERRIDES: dict[tuple[str, str], tuple[str, ...]] = {
    ("stock", "get_all_company_performance"): ("stock", "performance", "quarterly"),
    ("stock", "get_all_report_dates"): ("stock", "report-dates"),
    ("stock", "get_base_info"): ("stock", "profile"),
    ("stock", "get_belong_board"): ("stock", "sector"),
    ("stock", "get_daily_billboard"): ("stock", "leaderboard", "daily"),
    ("stock", "get_deal_detail"): ("stock", "trades"),
    ("stock", "get_history_bill"): ("stock", "flow", "history"),
    ("stock", "get_latest_holder_number"): ("stock", "holders", "latest-count"),
    ("stock", "get_latest_ipo_info"): ("stock", "ipo", "latest"),
    ("stock", "get_latest_quote"): ("stock", "price", "latest"),
    ("stock", "get_members"): ("stock", "constituents"),
    ("stock", "get_quote_history"): ("stock", "price", "history"),
    ("stock", "get_quote_snapshot"): ("stock", "price", "snapshot"),
    ("stock", "get_realtime_quotes"): ("stock", "price", "live"),
    ("stock", "get_today_bill"): ("stock", "flow", "today"),
    ("stock", "get_top10_stock_holder_info"): ("stock", "holders", "top10"),
    ("fund", "get_base_info"): ("fund", "profile"),
    ("fund", "get_fund_codes"): ("fund", "catalog"),
    ("fund", "get_fund_manager"): ("fund", "managers"),
    ("fund", "get_industry_distribution"): ("fund", "allocation", "industry"),
    ("fund", "get_invest_position"): ("fund", "allocation", "position"),
    ("fund", "get_pdf_reports"): ("fund", "reports", "download"),
    ("fund", "get_period_change"): ("fund", "performance", "period"),
    ("fund", "get_public_dates"): ("fund", "disclosure", "dates"),
    ("fund", "get_quote_history"): ("fund", "nav", "history"),
    ("fund", "get_quote_history_multi"): ("fund", "nav", "history-batch"),
    ("fund", "get_realtime_increase_rate"): ("fund", "estimate", "live"),
    ("fund", "get_types_percentage"): ("fund", "allocation", "types"),
    ("bond", "get_all_base_info"): ("bond", "catalog"),
    ("bond", "get_base_info"): ("bond", "profile"),
    ("bond", "get_deal_detail"): ("bond", "trades"),
    ("bond", "get_history_bill"): ("bond", "flow", "history"),
    ("bond", "get_quote_history"): ("bond", "price", "history"),
    ("bond", "get_realtime_quotes"): ("bond", "price", "live"),
    ("bond", "get_today_bill"): ("bond", "flow", "today"),
    ("futures", "get_deal_detail"): ("futures", "trades"),
    ("futures", "get_futures_base_info"): ("futures", "catalog"),
    ("futures", "get_quote_history"): ("futures", "price", "history"),
    ("futures", "get_realtime_quotes"): ("futures", "price", "live"),
    ("common", "get_base_info"): ("quote", "profile"),
    ("common", "get_deal_detail"): ("quote", "trades"),
    ("common", "get_history_bill"): ("quote", "flow", "history"),
    ("common", "get_latest_quote"): ("quote", "price", "latest"),
    ("common", "get_quote_history"): ("quote", "price", "history"),
    ("common", "get_realtime_quotes_by_fs"): ("market", "price", "live"),
    ("common", "get_today_bill"): ("quote", "flow", "today"),
    ("utils", "add_market"): ("market", "add"),
    ("utils", "get_quote_id"): ("resolve", "quote-id"),
    ("utils", "search_quote"): ("search",),
    ("utils", "search_quote_locally"): ("search", "local"),
}

FUNCTION_HELP_OVERRIDES: dict[tuple[str, str], str] = {
    ("stock", "get_all_company_performance"): "获取沪深市场股票某一季度的表现情况。",
    ("stock", "get_all_report_dates"): "获取沪深市场的全部股票报告期信息。",
    ("stock", "get_base_info"): "获取单只或多只股票的基础资料。",
    ("stock", "get_belong_board"): "获取股票所属板块。",
    ("stock", "get_daily_billboard"): "获取指定日期区间的龙虎榜详情数据。",
    ("stock", "get_deal_detail"): "获取股票最新交易日成交明细。",
    ("stock", "get_history_bill"): "获取单只股票历史单子流入流出数据。",
    ("stock", "get_latest_holder_number"): "获取最新公开股东户数变化情况。",
    ("stock", "get_latest_ipo_info"): "获取企业 IPO 审核状态。",
    ("stock", "get_latest_quote"): "获取多只股票最新价格与涨跌情况。",
    ("stock", "get_members"): "获取指数成分股信息。",
    ("stock", "get_quote_history"): "获取股票 K 线历史数据。",
    ("stock", "get_quote_snapshot"): "获取股票当前行情快照。",
    ("stock", "get_realtime_quotes"): "获取股票市场实时行情列表。",
    ("stock", "get_today_bill"): "获取股票最新交易日日内资金流。",
    ("stock", "get_top10_stock_holder_info"): "获取指定股票前十大股东信息。",
    ("fund", "get_base_info"): "获取单只或多只基金的基础资料。",
    ("fund", "get_fund_codes"): "获取全部公募基金名录。",
    ("fund", "get_fund_manager"): "获取基金管理人信息。",
    ("fund", "get_industry_distribution"): "获取基金行业分布信息。",
    ("fund", "get_invest_position"): "获取基金持仓占比数据。",
    ("fund", "get_pdf_reports"): "下载基金报告到指定目录。",
    ("fund", "get_period_change"): "获取基金阶段涨跌幅度。",
    ("fund", "get_public_dates"): "获取历史持仓披露日期列表。",
    ("fund", "get_quote_history"): "获取基金历史净值信息。",
    ("fund", "get_quote_history_multi"): "批量获取基金历史净值信息。",
    ("fund", "get_realtime_increase_rate"): "获取基金实时估算涨跌幅。",
    ("fund", "get_types_percentage"): "获取基金不同类型占比信息。",
    ("bond", "get_all_base_info"): "获取全部债券基本信息列表。",
    ("bond", "get_base_info"): "获取单只或多只债券基础资料。",
    ("bond", "get_deal_detail"): "获取债券最新交易日成交明细。",
    ("bond", "get_history_bill"): "获取单只债券历史资金流。",
    ("bond", "get_quote_history"): "获取债券 K 线历史数据。",
    ("bond", "get_realtime_quotes"): "获取债券市场实时行情列表。",
    ("bond", "get_today_bill"): "获取债券最新交易日日内资金流。",
    ("futures", "get_deal_detail"): "获取期货最新交易日成交明细。",
    ("futures", "get_futures_base_info"): "获取全部期货基础信息列表。",
    ("futures", "get_quote_history"): "获取期货历史行情信息。",
    ("futures", "get_realtime_quotes"): "获取期货实时行情列表。",
    ("common", "get_base_info"): "基于通用行情标识获取基础资料。",
    ("common", "get_deal_detail"): "基于通用行情标识获取成交明细。",
    ("common", "get_history_bill"): "基于通用行情标识获取历史资金流。",
    ("common", "get_latest_quote"): "基于通用行情标识获取最新行情。",
    ("common", "get_quote_history"): "基于通用行情标识获取历史行情。",
    ("common", "get_realtime_quotes_by_fs"): "按市场过滤串获取实时行情列表。",
    ("common", "get_today_bill"): "基于通用行情标识获取日内资金流。",
    ("utils", "search_quote"): "根据关键字搜索证券候选项。",
    ("utils", "search_quote_locally"): "仅使用本地缓存搜索证券候选项。",
    ("utils", "get_quote_id"): "把证券关键字或代码解析为东方财富行情 ID。",
    ("utils", "add_market"): "向本地市场分类映射中追加市场定义。",
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


def search_quote_compat(
    keyword: str,
    market_type: Any = None,
    result_count: int = 5,
    use_local: bool = True,
) -> Any:
    """兼容封装 `efinance.utils.search_quote` 的 CLI 参数语义。"""
    return efinance.utils.search_quote(
        keyword=keyword,
        market_type=market_type,
        count=result_count,
        use_local=use_local,
    )


CALLBACK_OVERRIDES[("utils", "search_quote")] = with_network_retry(search_quote_compat)


def get_module(module_name: str) -> Any:
    """根据模块名获取 efinance 子模块。"""
    try:
        return getattr(efinance, module_name)
    except AttributeError as exc:
        raise KeyError(f"未知模块: {module_name}") from exc


def list_root_group_names() -> list[str]:
    """返回当前用户可见的根命令组名称列表。"""
    return list(VISIBLE_ROOT_GROUPS)


def build_command_specs_for_group(group_name: str) -> list[CommandSpec]:
    """按用户可见根分组收集命令规格。"""
    specs: list[CommandSpec] = []
    for module_name in ALLOWED_FUNCTIONS:
        for spec in build_command_specs(module_name):
            if spec.cli_path and spec.cli_path[0] == group_name:
                specs.append(spec)
    specs.sort(key=lambda item: item.cli_path)
    return specs


def build_command_specs(module_name: str) -> list[CommandSpec]:
    """为指定上游模块构建命令描述列表。"""
    module = get_module(module_name)
    specs: list[CommandSpec] = []
    allowed = ALLOWED_FUNCTIONS[module_name]
    for name in sorted(item for item in dir(module) if not item.startswith("_")):
        if name not in allowed:
            continue
        obj = getattr(module, name)
        key = (module_name, name)
        callback = CALLBACK_OVERRIDES.get(key, obj)
        if callback is obj:
            callback = with_network_retry(callback)
        inspected_obj = inspect.unwrap(obj)
        if not callable(inspected_obj):
            continue
        module_path = getattr(inspected_obj, "__module__", "")
        if module_name != "utils" and not module_path.startswith(module.__name__):
            continue
        doc = inspect.getdoc(callback) or inspect.getdoc(inspected_obj) or ""
        help_text = FUNCTION_HELP_OVERRIDES.get(key) or doc.splitlines()[0] if doc else f"{module_name}.{name}"
        cli_path = CLI_PATH_OVERRIDES.get(key)
        if cli_path is None:
            raise KeyError(f"Missing CLI path override for command: {module_name}.{name}")
        specs.append(
            CommandSpec(
                module_name=module_name,
                function_name=name,
                callback=callback,
                help_text=help_text,
                cli_path=cli_path,
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
