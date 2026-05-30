"""命令执行与循环刷新管线。

该模块负责把一次 CLI 调用稳定地串成固定流程：参数标准化、第三方函数调用、
结果增强、渲染与输出。`watch` 只是对同一执行骨架做重复调度，不应把刷新逻辑
侵入到各个业务命令内部。
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any

import click
import pandas as pd

from efinance_cli.facade import CommandFacade
from efinance_cli.enrichment import enrich_market_data
from efinance_cli.introspection import build_parameter_specs, coerce_parameter_value
from efinance_cli.models import InvocationRequest, InvocationResult
from efinance_cli.observation import build_observation_output
from efinance_cli.request_schema import validate_request_data
from efinance_cli.rendering import render_value


class CommandExecutor:
    """执行命令请求的统一入口。"""

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        """执行一次命令请求。"""
        if request.command_definition is not None and request.backend_selection is not None:
            value = self._execute_shared_command(request)
        else:
            value = self._execute_legacy_command(request)
        value = enrich_market_data(request, value)
        value = build_observation_output(request, value)
        return InvocationResult(value=value)

    def run(self, request: InvocationRequest) -> None:
        """根据刷新配置执行一次或多次调用。"""
        if request.watch.enabled:
            self._run_watch(request)
            return
        result = self.invoke(request)
        self._emit(request, result)

    def _run_watch(self, request: InvocationRequest) -> None:
        """循环刷新执行。"""
        if not request.spec.allow_watch:
            raise click.ClickException(
                f"{request.spec.module_name}.{request.spec.function_name} does not support watch mode."
            )

        iteration = 0
        while True:
            iteration += 1
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
        """输出结果到控制台或文件。"""
        text = self._render(request, result)
        if request.output.output_path:
            output_path = Path(request.output.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding=request.output.encoding)
        click.echo(text)

    def _render(self, request: InvocationRequest, result: InvocationResult) -> str:
        """渲染结果文本。"""
        return render_value(result.value, request.output)

    def _execute_legacy_command(self, request: InvocationRequest) -> Any:
        """执行旧的函数驱动命令路径。"""

        kwargs = self._normalize_kwargs(request)
        return request.spec.callback(**kwargs)

    def _execute_shared_command(self, request: InvocationRequest) -> Any:
        """执行基于共享命令目录的新调用路径。"""

        assert request.command_definition is not None
        assert request.backend_selection is not None

        request_data = validate_request_data(
            request.command_definition.request_schema,
            request.kwargs,
        )
        facade = CommandFacade()
        standard_result = facade.invoke(
            request.command_definition,
            request.backend_selection,
            request_data,
        )
        request.kwargs = {
            **request.kwargs,
            **request_data,
        }
        return self._materialize_standard_result(request, standard_result)

    def _normalize_kwargs(self, request: InvocationRequest) -> dict[str, Any]:
        """按函数签名把 CLI 输入转换为真实调用参数。"""
        specs = {spec.name: spec for spec in build_parameter_specs(request.spec.callback)}
        normalized: dict[str, Any] = {}
        for key, value in request.kwargs.items():
            spec = specs.get(key)
            if spec is None:
                normalized[key] = value
                continue
            if isinstance(value, tuple) and not spec.is_variadic:
                value = value[0] if len(value) == 1 else list(value)
            normalized[key] = coerce_parameter_value(spec.annotation, value)
        return normalized

    def _materialize_standard_result(self, request: InvocationRequest, standard_result: Any) -> Any:
        """把标准结果封装转换为现有渲染链可消费的对象。

        设计约束：
        - `observation` 仍然只消费标准化后的主体数据；
        - `raw` 视图需要保留契约名、原始 payload 和 provider 扩展字段；
        - 表格/JSON/CSV/TSV 渲染仍然复用现有渲染层，不为共享命令单独开旁路。
        """

        data = getattr(standard_result, "data", standard_result)
        materialized = data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            materialized = self._materialize_standard_rows(request, data)

        if request.output.view_mode == "raw":
            return {
                "contract_name": getattr(standard_result, "contract_name", None),
                "data": data,
                "raw_payload": getattr(standard_result, "raw_payload", None),
                "provider_fields": getattr(standard_result, "provider_fields", {}),
                "metadata": getattr(standard_result, "metadata", {}),
            }
        return materialized

    def _materialize_standard_rows(
        self,
        request: InvocationRequest,
        rows: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """把共享契约记录转换为标准字段 DataFrame。

        这里不再把共享结果重新回投成旧的 provider 原始列名，后续增强与 observation
        应直接消费标准契约字段，兼容下沉到标准化与补充接口层处理。
        """

        _ = request
        return pd.DataFrame(rows)


def build_request_kwargs(function: Any, raw_kwargs: dict[str, Any]) -> dict[str, Any]:
    """从 Click 参数中提取真实业务参数。"""
    signature = inspect.signature(function)
    valid_names = set(signature.parameters.keys())
    result: dict[str, Any] = {}
    for key, value in raw_kwargs.items():
        if key in valid_names:
            result[key] = value
    return result


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
    """计算 watch 的刷新次数配置。"""
    return count
