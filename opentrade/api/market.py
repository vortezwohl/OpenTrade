"""市场域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class MarketNamespace(ApiNamespace):
    """封装 `market` 命令域的程序化入口。"""

    def add(
        self,
        market_category: str,
        market_id: str,
        market_name: str,
        *,
        deduplicate: bool = True,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """新增市场映射配置。"""
        return self._execute(
            "market.add",
            {
                "category": market_category,
                "market_number": market_id,
                "market_name": market_name,
                "drop_duplicate": deduplicate,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def price_live(
        self,
        market: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询市场级实时行情。"""
        return self._execute(
            "market.price.live",
            {"fs": market},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
