"""统一命令执行器。

这里串起 shared / provider-extension 命令的公共执行链，
负责 CLI 请求标准化、backend 调用、结果物化与渲染输出，
并保证 observation、raw 与 `watch` 走同一套执行语义。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import click
import pandas as pd

from opentrade.backends.auto_planner import plan_auto_backend_candidates
from opentrade.enrichment import enrich_market_data
from opentrade.facade import CommandFacade
from opentrade.models import InvocationRequest, InvocationResult, LimitStrategy
from opentrade.observation import build_observation_output
from opentrade.rendering import render_value
from opentrade.request_schema import validate_request_data


class CommandExecutor:
    """统一执行单次命令调用。"""

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        """执行并返回结构化结果。"""
        if request.command_definition is None or request.backend_selection is None:
            raise click.ClickException("Legacy function-driven commands are no longer supported.")
        if request.backend_selection.is_auto:
            request.backend_selection.final_backend = None
            request.backend_selection.attempted_candidates.clear()
            request.backend_selection.fallback_used = False
        value = self._execute_shared_command(request)
        if request.output.view_mode != "raw":
            value = enrich_market_data(request, value)
            value = build_observation_output(request, value)
        return InvocationResult(value=value)

    def run(self, request: InvocationRequest) -> None:
        """执行请求并直接输出到终端或文件。"""
        if request.watch.enabled:
            self._run_watch(request)
            return
        result = self.invoke(request)
        self._emit(request, result)

    def _run_watch(self, request: InvocationRequest) -> None:
        """以 watch 模式重复执行请求。"""
        if not request.spec.allow_watch:
            raise click.ClickException(
                f"{request.spec.module_name}.{request.spec.function_name} does not support watch mode."
            )

        iteration = 0
        while True:
            iteration += 1
            if request.backend_selection is not None and request.backend_selection.is_auto:
                request.backend_selection.final_backend = None
                request.backend_selection.attempted_candidates.clear()
                request.backend_selection.fallback_used = False
            result = self.invoke(request)
            if request.watch.clear_screen:
                click.clear()
            header = (
                f"[watch] {request.spec.module_name}.{request.spec.function_name} "
                f"refresh #{iteration}, interval {request.watch.interval}s"
            )
            click.echo(header)
            click.echo(self._render(request, result))

            if request.watch.count is not None and iteration >= request.watch.count:
                break
            time.sleep(request.watch.interval)

    def _emit(self, request: InvocationRequest, result: InvocationResult) -> None:
        """输出最终渲染结果。"""
        text = self._render(request, result)
        if request.output.output_path:
            output_path = Path(request.output.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding=request.output.encoding)
        click.echo(self._sanitize_console_text(text))

    @staticmethod
    def _render(request: InvocationRequest, result: InvocationResult) -> str:
        """渲染执行结果。"""
        return render_value(result.value, request.output)

    @staticmethod
    def _sanitize_console_text(text: str) -> str:
        """在控制台输出前降级不兼容字符，避免 Windows GBK 终端报错。"""

        encoding = sys.stdout.encoding or "utf-8"
        try:
            text.encode(encoding)
            return text
        except UnicodeEncodeError:
            return text.encode(encoding, errors="replace").decode(
                encoding,
                errors="replace",
            )

    def _execute_shared_command(self, request: InvocationRequest) -> Any:
        """执行 shared 命令并返回标准结果。"""

        assert request.command_definition is not None
        assert request.backend_selection is not None

        request_data = validate_request_data(
            request.command_definition.request_schema,
            request.kwargs,
        )
        if request.backend_selection.is_auto:
            request.backend_selection.candidate_chain = plan_auto_backend_candidates(
                request.command_definition,
                request_data,
            )
            if not request.backend_selection.candidate_chain:
                raise click.ClickException(
                    f"命令 '{' '.join(request.command_definition.cli_path)}' 没有可用的 auto backend 候选"
                )
        facade = CommandFacade()
        standard_result = facade.invoke(
            request.command_definition,
            request.backend_selection,
            request_data,
            execution_limit=request.output.limit,
        )
        request.kwargs = {
            **request.kwargs,
            **request_data,
        }
        return self._materialize_standard_result(request, standard_result)

    @staticmethod
    def _build_limit_metadata(request: InvocationRequest, standard_result: Any) -> dict[str, Any]:
        """根据 provider 元数据判定 `--limit` 的真实执行语义。"""

        limit_value = request.output.limit
        strategy = request.command_definition.limit_strategy
        effect = "none"
        execution_limit_applied = False
        display_limit_applied = False

        if limit_value is not None:
            provider_metadata = getattr(standard_result, "metadata", {}) or {}
            execution_limit_applied = bool(provider_metadata.get("execution_limit_applied", False))
            display_limit_applied = True
            if execution_limit_applied:
                effect = "execution-aware"
            else:
                strategy_enum = LimitStrategy(strategy)
                if strategy_enum == LimitStrategy.DISPLAY_ONLY:
                    effect = "display-only"
                else:
                    effect = "declared-but-not-applied"

        return {
            "limit_strategy": strategy,
            "limit_value": limit_value,
            "limit_effect": effect,
            "display_limit_applied": display_limit_applied,
            "execution_limit_applied": execution_limit_applied,
        }

    def _materialize_standard_result(self, request: InvocationRequest, standard_result: Any) -> Any:
        """把标准结果物化成 rendering 可消费的结构。"""

        data = getattr(standard_result, "data", standard_result)
        materialized = data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            materialized = self._materialize_standard_rows(request, data)
        elif isinstance(data, dict) and self._is_standard_row_mapping(data):
            materialized = {
                key: self._materialize_standard_rows(request, value)
                for key, value in data.items()
            }
        elif isinstance(data, dict) and getattr(standard_result, "contract_name", None) == "profile-info":
            materialized = pd.Series(data)

        if request.output.view_mode == "raw":
            backend_selection = request.backend_selection
            backend_metadata = {
                "requested_backend": (
                    backend_selection.requested.value
                    if backend_selection is not None and backend_selection.requested is not None
                    else None
                ),
                "resolved_backend": (
                    backend_selection.resolved.value
                    if backend_selection is not None
                    else None
                ),
                "planned_candidates": (
                    [item.value for item in backend_selection.candidate_chain]
                    if backend_selection is not None
                    else []
                ),
                "attempted_candidates": (
                    [item.value for item in backend_selection.attempted_candidates]
                    if backend_selection is not None
                    else []
                ),
                "final_backend": (
                    backend_selection.final_backend.value
                    if backend_selection is not None and backend_selection.final_backend is not None
                    else None
                ),
                "fallback_used": (
                    backend_selection.fallback_used
                    if backend_selection is not None
                    else False
                ),
                **self._build_limit_metadata(request, standard_result),
            }
            return {
                "contract_name": getattr(standard_result, "contract_name", None),
                "data": data,
                "raw_payload": getattr(standard_result, "raw_payload", None),
                "provider_fields": getattr(standard_result, "provider_fields", {}),
                "metadata": {
                    **getattr(standard_result, "metadata", {}),
                    **backend_metadata,
                },
            }
        return materialized

    def _materialize_standard_rows(
        self,
        request: InvocationRequest,
        rows: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """把标准行记录转换成 DataFrame。"""

        _ = request
        return pd.DataFrame(rows)

    def _is_standard_row_mapping(self, value: dict[str, Any]) -> bool:
        """判断字典是否是 `source -> rows` 形式的标准结果。"""

        if not value:
            return True
        for item in value.values():
            if item == []:
                continue
            if not isinstance(item, list):
                return False
            if item and not isinstance(item[0], dict):
                return False
        return True


def split_runtime_options(raw_kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """拆分业务参数与 CLI 运行时参数。"""
    runtime_keys = {
        "format_name",
        "full",
        "transpose",
        "no_index",
        "limit",
        "output_path",
        "encoding",
        "indicator_level",
        "view_mode",
        "trace_window",
        "watch",
        "interval",
        "count",
        "clear_screen",
        "backend_name",
    }
    runtime: dict[str, Any] = {}
    business: dict[str, Any] = {}
    for key, value in raw_kwargs.items():
        if key in runtime_keys:
            runtime[key] = value
        else:
            business[key] = value
    return business, runtime


def default_watch_count(enabled: bool, count: int | None) -> int | None:
    """返回 watch 模式的默认执行次数。"""
    _ = enabled
    return count
