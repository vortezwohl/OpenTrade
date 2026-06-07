"""解析域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class ResolveNamespace(ApiNamespace):
    """封装 `resolve` 命令域的程序化入口。"""

    def quote_id(
        self,
        symbol: str,
        *,
        market: str | None = None,
        use_local_cache: bool = True,
        ignore_errors: bool = False,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """解析共享 symbol 到 quote_id。"""
        return self._execute(
            "resolve.quote-id",
            {
                "stock_code": symbol,
                "market_type": market,
                "use_local": use_local_cache,
                "suppress_error": ignore_errors,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
