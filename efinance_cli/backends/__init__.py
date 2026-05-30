"""多后端 provider 架构入口。

这里先暴露 provider、handler、resolver 和 facade 的骨架类型，供命令目录与执行层
逐步迁移使用。当前阶段不追求覆盖全部能力，只要求新架构可以稳定承载首批共享命令。
"""

from efinance_cli.backends.base import BackendProvider, CapabilityHandler
from efinance_cli.backends.factory import get_backend_provider, list_backend_providers
from efinance_cli.backends.resolver import resolve_backend_selection

__all__ = [
    "BackendProvider",
    "CapabilityHandler",
    "get_backend_provider",
    "list_backend_providers",
    "resolve_backend_selection",
]
