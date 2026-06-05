"""CLI 主入口模块。

该文件只负责把 click 命令树暴露给解释器，不承载具体业务逻辑。 真正的命令构建、执行编排与结果渲染分别下沉到
`app`、`executor` 与 `rendering` 子模块中，避免入口文件逐渐演变成难以维护的巨型脚本。
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from opentrade.app import create_cli


def main() -> None:
    """启动命令行应用。"""
    create_cli()()


if __name__ == "__main__":
    main()
