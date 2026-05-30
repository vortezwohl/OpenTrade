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


def get_backend_provider(backend_name: BackendName) -> BackendProvider:
    """按 backend 名称返回 provider。"""

    registry = list_backend_providers()
    try:
        return registry[backend_name]
    except KeyError as exc:
        raise KeyError(f"未知 backend: {backend_name.value}") from exc
