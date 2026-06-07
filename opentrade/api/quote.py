"""通用行情域的对象式程序化 API。

该模块对应 `quote` 命令域，覆盖共享行情历史、最新行情、资料，以及
通用资金流、成交明细和新闻等扩展能力。
"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class QuoteNamespace(ApiNamespace):
    """封装 `quote` 命令域的程序化入口。"""

    def price_history(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        start_date: str = "19000101",
        end_date: str = "20500101",
        timeframe: int = 101,
        adjustment: int = 1,
        market: str | None = None,
        ignore_errors: bool = False,
        use_id_cache: bool = True,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情历史价格。"""
        return self._execute(
            "quote.price.history",
            {
                "symbols": list(symbols),
                "start_date": start_date,
                "end_date": end_date,
                "timeframe": timeframe,
                "adjustment": adjustment,
                "market": market,
                "ignore_errors": ignore_errors,
                "use_id_cache": use_id_cache,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_latest(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情最新价格。"""
        return self._execute(
            "quote.price.latest",
            {"symbols": list(symbols)},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def profile(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情资料。"""
        return self._execute(
            "quote.profile",
            {"symbol": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def flow_history(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情历史资金流。"""
        return self._execute(
            "quote.flow.history",
            {"code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def flow_today(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情日内资金流。"""
        return self._execute(
            "quote.flow.today",
            {"code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def trades(
        self,
        quote_id: str,
        *,
        max_records: int = 1_000_000,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情成交明细。"""
        return self._execute(
            "quote.trades",
            {
                "quote_id": quote_id,
                "max_count": max_records,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def news(
        self,
        quote_id: str,
        *,
        result_count: int = 10,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询通用行情相关新闻。

        当前命令由 yfinance provider 专属扩展提供。
        """
        return self._execute(
            "yfinance.quote.news",
            {
                "quote_id": quote_id,
                "result_count": result_count,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
