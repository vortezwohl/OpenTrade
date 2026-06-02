"""`python -m opentrade` 的模块入口。

该文件保持极薄封装，只做一件事：转调标准主入口 `opentrade.main`。
这样既兼容包脚本方式启动，也兼容模块方式启动。
"""

from opentrade.main import main


if __name__ == "__main__":
    main()
