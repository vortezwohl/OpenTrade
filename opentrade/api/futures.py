"""期货域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class FuturesNamespace(ApiNamespace):
    """封装 `futures` 命令域的程序化入口。"""

    def catalog(
        self,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询期货名录。"""
        return self._execute(
            "futures.catalog",
            {},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_history(
        self,
        quote_ids: list[str] | tuple[str, ...],
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
        """查询期货历史价格。"""
        return self._execute(
            "futures.price.history",
            {
                "quote_ids": list(quote_ids),
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
        """查询期货实时行情。"""
        return self._execute(
            "futures.price.live",
            {},
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
        """查询期货成交明细。"""
        return self._execute(
            "futures.trades",
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
