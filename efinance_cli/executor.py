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

from efinance_cli.enrichment import enrich_market_data
from efinance_cli.introspection import build_parameter_specs, coerce_parameter_value
from efinance_cli.models import InvocationRequest, InvocationResult
from efinance_cli.observation import build_observation_output
from efinance_cli.rendering import render_value


class CommandExecutor:
    """执行命令请求的统一入口。"""

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        """执行一次命令请求。"""
        kwargs = self._normalize_kwargs(request)
        value = request.spec.callback(**kwargs)
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
