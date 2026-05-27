"""`python -m efinance_cli` 的模块入口。

该文件保持极薄封装，只做一件事：转调标准主入口 `efinance_cli.main`。
这样既兼容包脚本方式启动，也兼容模块方式启动。
"""

from efinance_cli.main import main


if __name__ == "__main__":
    main()
