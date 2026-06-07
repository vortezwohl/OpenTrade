"""OpenTrade 对象式程序化入口。

该模块定义 `OpenTrade` 类，用于把各个业务域命名空间组合成统一、显式、
稳定的 Python SDK 入口。调用方可以通过：

```python
from opentrade import OpenTrade

ot = OpenTrade()
result = ot.stock.price_history(symbols=["AAPL"])
```

直接复用现有命令执行链，而无需拼装 CLI 命令或 import 内部实现模块。
"""

from __future__ import annotations

from opentrade.api._runtime import ApiRuntime
from opentrade.api.bond import BondNamespace
from opentrade.api.fund import FundNamespace
from opentrade.api.futures import FuturesNamespace
from opentrade.api.market import MarketNamespace
from opentrade.api.quote import QuoteNamespace
from opentrade.api.resolve import ResolveNamespace
from opentrade.api.search import SearchNamespace
from opentrade.api.stock import StockNamespace


class OpenTrade:
    """面向其他 Python 程序的对象式 OpenTrade 入口。

    该对象把程序化 API 按业务域拆分为多个显式命名空间属性，目标是让：

    - 顶层导入稳定且简单；
    - IDE 自动补全可以逐层探索能力；
    - SDK 与 CLI 共享统一的命令执行语义。
    """

    def __init__(self) -> None:
        """初始化所有业务域命名空间。"""
        runtime = ApiRuntime()
        self.search = SearchNamespace(runtime)
        self.quote = QuoteNamespace(runtime)
        self.stock = StockNamespace(runtime)
        self.fund = FundNamespace(runtime)
        self.bond = BondNamespace(runtime)
        self.futures = FuturesNamespace(runtime)
        self.market = MarketNamespace(runtime)
        self.resolve = ResolveNamespace(runtime)
