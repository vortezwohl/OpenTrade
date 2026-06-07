"""基金域的对象式程序化 API。"""

from __future__ import annotations

from typing import Any

from opentrade.api._runtime import ApiNamespace, BackendValue, ViewMode


class FundNamespace(ApiNamespace):
    """封装 `fund` 命令域的程序化入口。"""

    def nav_history(
        self,
        symbol: str,
        *,
        max_pages: int = 40000,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金历史净值。"""
        return self._execute(
            "fund.nav.history",
            {
                "symbol": symbol,
                "max_pages": max_pages,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def nav_history_batch(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        max_pages: int = 40000,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """批量查询基金历史净值。"""
        return self._execute(
            "fund.nav.history-batch",
            {
                "fund_codes": list(symbols),
                "pz": max_pages,
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
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金资料。"""
        return self._execute(
            "fund.profile",
            {"symbol": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def catalog(
        self,
        *,
        fund_type: str | None = None,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金名录。"""
        return self._execute(
            "fund.catalog",
            {"ft": fund_type},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def managers(
        self,
        fund_type: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金管理人。"""
        return self._execute(
            "fund.managers",
            {"ft": fund_type},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def estimate_live(
        self,
        symbols: list[str] | tuple[str, ...],
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金实时估算。"""
        return self._execute(
            "fund.estimate.live",
            {"fund_codes": list(symbols)},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def performance_period(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金阶段表现。"""
        return self._execute(
            "fund.performance.period",
            {"fund_code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def disclosure_dates(
        self,
        symbol: str,
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金披露日期。"""
        return self._execute(
            "fund.disclosure.dates",
            {"fund_code": symbol},
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def allocation_industry(
        self,
        symbol: str,
        *,
        dates: list[str] | tuple[str, ...] = (),
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金行业分布。"""
        return self._execute(
            "fund.allocation.industry",
            {
                "fund_code": symbol,
                "dates": list(dates),
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def allocation_position(
        self,
        symbol: str,
        *,
        dates: list[str] | tuple[str, ...] = (),
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金持仓占比。"""
        return self._execute(
            "fund.allocation.position",
            {
                "fund_code": symbol,
                "dates": list(dates),
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def allocation_types(
        self,
        symbol: str,
        *,
        dates: list[str] | tuple[str, ...] = (),
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """查询基金类型占比。"""
        return self._execute(
            "fund.allocation.types",
            {
                "fund_code": symbol,
                "dates": list(dates),
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )

    def reports_download(
        self,
        symbol: str,
        *,
        max_files: int = 12,
        output_dir: str = "pdf",
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """下载基金报告。"""
        return self._execute(
            "fund.reports.download",
            {
                "fund_code": symbol,
                "max_count": max_files,
                "save_dir": output_dir,
            },
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
