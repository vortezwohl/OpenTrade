"""多后端 provider 的基础协议与实现骨架。

该模块定义新的最小调用单元：

- `CapabilityHandler`：处理单个 capability；
- `BackendProvider`：声明 provider 身份、支持矩阵和扩展命令占位。

当前阶段使用普通基类而不是协议或抽象基类，是为了让首批骨架更容易落地和打桩测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from efinance_cli.models import BackendName, CommandDefinition, StandardResult


class CapabilityHandler:
    """定义 capability handler 的最小接口。"""

    capability_name: str

    def execute(self, request_data: dict[str, Any]) -> StandardResult:
        """执行能力请求并返回标准结果。"""

        raise NotImplementedError


@dataclass(slots=True)
class BackendProvider:
    """定义 backend provider 的稳定元数据与 handler 注册表。

    Args:
        backend_name: provider 名称。
        handlers: capability -> handler 映射。
        extension_commands: provider 专属扩展命令定义。
    """

    backend_name: BackendName
    handlers: dict[str, CapabilityHandler] = field(default_factory=dict)
    extension_commands: tuple[CommandDefinition, ...] = field(default_factory=tuple)

    def supports(self, capability_name: str) -> bool:
        """判断 provider 是否支持指定 capability。"""

        return capability_name in self.handlers

    def get_handler(self, capability_name: str) -> CapabilityHandler:
        """返回 capability handler。"""

        try:
            return self.handlers[capability_name]
        except KeyError as exc:
            raise KeyError(
                f"Backend '{self.backend_name.value}' 不支持 capability '{capability_name}'"
            ) from exc
