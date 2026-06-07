"""OpenTrade 程序化 API 的公开入口。

该子包负责为其他 Python 程序暴露稳定、显式、便于 IDE 补全的对象式
SDK 入口。与 CLI 层不同，这里的职责不是拼装终端命令，而是把现有命令
目录、请求校验、后端路由与执行链封装成可直接 import 的 Python 对象。

当前版本只导出 `OpenTrade` 作为推荐入口，技术指标仍保持在
`opentrade.indicators` 子包中。
"""

from opentrade.api.client import OpenTrade

__all__ = ["OpenTrade"]
