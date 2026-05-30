"""统一命令门面。

命令层只需要关心“命令定义 + backend 选择 + 请求数据”，provider 查找与 handler 调用
都应由门面协调，避免再把 backend 条件分支散落回命令回调中。
"""

from __future__ import annotations

from efinance_cli.backends.factory import get_backend_provider
from efinance_cli.models import BackendSelection, CommandDefinition, StandardResult


class CommandFacade:
    """统一命令调用入口。"""

    def invoke(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
    ) -> StandardResult:
        """执行命令定义绑定的 capability。"""

        provider = get_backend_provider(backend.resolved)
        handler = provider.get_handler(definition.capability)
        return handler.execute(request_data)
