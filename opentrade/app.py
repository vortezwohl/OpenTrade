"""应用装配入口。

该模块负责把命令构建层与主入口连接起来，使外部只需要通过 `create_cli`
即可获得完整命令树。保持这一层薄，可以减少后续在入口和装配逻辑上的耦合。
"""

from opentrade.commands import create_root_command


def create_cli():
    """创建并返回根命令。"""
    return create_root_command()
