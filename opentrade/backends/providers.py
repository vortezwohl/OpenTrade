"""多后端 provider 模块的兼容导出层。

该模块保留旧的聚合导出入口，供工厂与测试在 provider 已拆分到独立文件后 继续通过单一模块访问共享 helper、handler 与
provider 构建函数。
"""

from __future__ import annotations

from opentrade.backends import akshare_provider as _akshare_provider
from opentrade.backends import efinance_provider as _efinance_provider
from opentrade.backends import yfinance_provider as _yfinance_provider
from opentrade.backends import providers_common as _providers_common

for _module in (
        _providers_common,
        _efinance_provider,
        _akshare_provider,
        _yfinance_provider,
):
    for _name, _value in vars(_module).items():
        if _name.startswith('__'):
            continue
        globals()[_name] = _value

del _module
del _name
del _value


def __dir__() -> list[str]:
    return sorted(name for name in globals() if not name.startswith('__'))
