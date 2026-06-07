"""OpenTrade 包的公开入口与版本信息。

该包同时服务两类主要调用方式：

1. 命令行入口：通过统一命令树暴露市场数据查询、输出渲染与观察视图；
2. 程序化入口：通过 `OpenTrade` 对象式 SDK 暴露可 import 的 Python API。

技术指标计算函数仍然通过 `opentrade.indicators` 子包单独导入，不混入
顶层对象式入口。
"""

from opentrade.api import OpenTrade

__all__ = ["OpenTrade", "__version__"]

__version__ = "1.1.0"
