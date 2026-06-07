"""债券域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class BondNamespace(ApiNamespace):
    """封装 `bond` 命令域的程序化入口。"""

    def catalog(
        self,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询债券名录。"""
        return self._execute(
            "bond.catalog",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_history(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        start_date: str = "19000101",
        end_date: str = "20500101",
        timeframe: int = 101,
        adjustment: int = 1,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询债券历史价格。"""
        return self._execute(
            "bond.price.history",
            {
                "bond_codes": list(symbols),
                "beg": start_date,
                "end": end_date,
                "klt": timeframe,
                "fqt": adjustment,
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
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询债券实时行情。"""
        return self._execute(
            "bond.price.live",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def profile(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询债券资料。"""
        return self._execute(
            "bond.profile",
            {"bond_codes": list(symbols)},
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
        """查询债券成交明细。"""
        return self._execute(
            "bond.trades",
            {
                "bond_code": symbol,
                "max_count": max_records,
            },
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
        """查询债券历史资金流。"""
        return self._execute(
            "bond.flow.history",
            {"bond_code": symbol},
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
        """查询债券日内资金流。"""
        return self._execute(
            "bond.flow.today",
            {"bond_code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
