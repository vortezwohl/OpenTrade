"""provider 注册表与获取入口。

该模块集中暴露当前可用 provider 以及它们声明的 provider-specific 扩展命令。
命令装配层不应再把 provider 名称直接暴露为顶层 CLI 根组，而应按扩展命令
自身声明的业务语义路径进行挂载。
"""

from __future__ import annotations

from efinance_cli.backends.base import BackendProvider
from efinance_cli.backends.providers import (
    build_akshare_provider,
    build_efinance_provider,
    build_yfinance_provider,
)
from efinance_cli.models import BackendName, CommandDefinition


def list_backend_providers() -> dict[BackendName, BackendProvider]:
    """返回当前已知 provider 的注册表。"""

    return {
        BackendName.EFINANCE: build_efinance_provider(),
        BackendName.AKSHARE: build_akshare_provider(),
        BackendName.YFINANCE: build_yfinance_provider(),
    }


def list_optional_provider_names() -> tuple[BackendName, ...]:
    """返回当前仅预留挂载点、尚未默认接入的 provider 名称。"""

    return ()


def get_backend_provider(backend_name: BackendName) -> BackendProvider:
    """按 backend 名称返回 provider。"""

    registry = list_backend_providers()
    try:
        return registry[backend_name]
    except KeyError as exc:
        raise KeyError(f"未知 backend: {backend_name.value}") from exc


def list_provider_extension_commands() -> tuple[CommandDefinition, ...]:
    """返回全部 provider 注册的扩展命令定义。"""

    definitions: list[CommandDefinition] = []
    for provider in list_backend_providers().values():
        definitions.extend(provider.extension_commands)
    return tuple(definitions)
