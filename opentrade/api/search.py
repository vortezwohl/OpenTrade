"""搜索域的对象式程序化 API。

该模块对应 CLI 中的 `search` 能力域，负责暴露：

- 通用标的搜索；
- 本地缓存搜索扩展命令。
"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class SearchNamespace(ApiNamespace):
    """封装 `search` 命令域的程序化入口。"""

    def instruments(
        self,
        keyword: str,
        *,
        market: str | None = None,
        result_count: int = 5,
        use_local_cache: bool = True,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """按关键词搜索可交易标的。

        Args:
            keyword: 搜索关键词。
            market: 可选市场枚举。
            result_count: 返回结果数量。
            use_local_cache: 是否优先使用本地缓存。
            backend: 可选 backend 名称。
            view: 返回视图模式。
            indicator_level: 指标增强等级。
            trace_window: observation 窗口长度。
            limit: 结果限制条数。

        Returns:
            搜索结果对应的 Python 对象。
        """
        return self._execute(
            "instrument.search",
            {
                "keyword": keyword,
                "market": market,
                "result_count": result_count,
                "use_local_cache": use_local_cache,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def local(
        self,
        keyword: str,
        *,
        market: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """使用本地缓存搜索标的。

        Args:
            keyword: 搜索关键词。
            market: 可选市场枚举。
            backend: 可选 backend 名称。
            view: 返回视图模式。
            indicator_level: 指标增强等级。
            trace_window: observation 窗口长度。
            limit: 结果限制条数。

        Returns:
            本地搜索结果。
        """
        return self._execute(
            "search.local",
            {
                "keyword": keyword,
                "market_type": market,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
