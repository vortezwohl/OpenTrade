"""股票域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class StockNamespace(ApiNamespace):
    """封装 `stock` 命令域的程序化入口。"""

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
        """查询股票历史 K 线行情。"""
        return self._execute(
            "stock.price.history",
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
        market: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询股票最新行情。"""
        return self._execute(
            "stock.price.latest",
            {
                "symbols": list(symbols),
                "market": market,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_live(
        self,
        *,
        market: str = "A_stock",
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询股票实时行情列表。"""
        return self._execute(
            "stock.price.live",
            {"market": market},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_snapshot(
        self,
        symbol: str,
        *,
        market: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询单只股票快照。"""
        return self._execute(
            "stock.price.snapshot",
            {
                "symbol": symbol,
                "market": market,
            },
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
        market: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询单只股票资料。"""
        return self._execute(
            "stock.profile",
            {
                "symbol": symbol,
                "market": market,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def constituents(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询指数成分股。"""
        return self._execute(
            "stock.constituents",
            {"index_code": symbol},
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
        """查询股票历史资金流。"""
        return self._execute(
            "stock.flow.history",
            {"stock_code": symbol},
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
        """查询股票日内资金流。"""
        return self._execute(
            "stock.flow.today",
            {"stock_code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def holders_latest_count(
        self,
        *,
        date: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询最新公开股东户数变化。"""
        return self._execute(
            "stock.holders.latest-count",
            {"date": date},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def holders_top10(
        self,
        symbol: str,
        *,
        top: int = 4,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询前十大股东。"""
        return self._execute(
            "stock.holders.top10",
            {
                "stock_code": symbol,
                "top": top,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def ipo_latest(
        self,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询最新 IPO 信息。"""
        return self._execute(
            "stock.ipo.latest",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def leaderboard_daily(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询龙虎榜日度信息。"""
        return self._execute(
            "stock.leaderboard.daily",
            {
                "start_date": start_date,
                "end_date": end_date,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def performance_quarterly(
        self,
        *,
        date: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询季度表现。"""
        return self._execute(
            "stock.performance.quarterly",
            {"date": date},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def report_dates(
        self,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询报告期列表。"""
        return self._execute(
            "stock.report-dates",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def sector(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询股票所属板块。"""
        return self._execute(
            "stock.sector",
            {"stock_code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def trades(
        self,
        symbol: str,
        *,
        max_records: int = 1_000_000,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询股票成交明细。"""
        return self._execute(
            "stock.trades",
            {
                "stock_code": symbol,
                "max_count": max_records,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def industry_boards(
        self,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """获取行业板块列表。"""
        return self._execute(
            "akshare.industry.boards",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
