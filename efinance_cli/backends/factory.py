"""provider 注册表与获取入口。"""

from __future__ import annotations

from efinance_cli.backends.base import BackendProvider
from efinance_cli.backends.providers import build_akshare_provider, build_efinance_provider
from efinance_cli.models import BackendName


def list_backend_providers() -> dict[BackendName, BackendProvider]:
    """返回当前已知 provider 的注册表。"""

    return {
        BackendName.EFINANCE: build_efinance_provider(),
        BackendName.AKSHARE: build_akshare_provider(),
    }


def list_optional_provider_names() -> tuple[BackendName, ...]:
    """返回当前仅预留挂载点、尚未默认接入的 provider 名称。"""

    return (BackendName.YFINANCE,)


def get_backend_provider(backend_name: BackendName) -> BackendProvider:
    """按 backend 名称返回 provider。"""

    registry = list_backend_providers()
    try:
        return registry[backend_name]
    except KeyError as exc:
        raise KeyError(f"未知 backend: {backend_name.value}") from exc


def list_provider_extension_commands() -> dict[BackendName, tuple]:
    """返回各 provider 注册的扩展命令定义。"""

    return {
        backend_name: provider.extension_commands
        for backend_name, provider in list_backend_providers().items()
        if provider.extension_commands
    }
